// Input e finestre reali di Windows per le prove: tasti e mouse passano dal sistema (keybd_event, mouse_event), come quelli
// dell'utente, quindi raggiungono anche i tasti globali e il menu dell'area di notifica.
// Un solo PowerShell resta aperto per tutta la prova: compilare il codice Win32 a ogni chiamata costerebbe secondi.
import { spawn } from 'node:child_process';
import { writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

const CS = String.raw`
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;

public static class QnWin {
  delegate bool EnumProc(IntPtr h, IntPtr l);
  [DllImport("user32.dll")] static extern bool EnumWindows(EnumProc f, IntPtr l);
  [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetWindowText(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetClassName(IntPtr h, StringBuilder s, int n);
  [DllImport("user32.dll")] static extern bool IsWindowVisible(IntPtr h);
  [DllImport("user32.dll")] static extern bool IsZoomed(IntPtr h);
  [DllImport("user32.dll")] static extern bool IsIconic(IntPtr h);
  [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out RECT r);
  [DllImport("user32.dll")] static extern bool ClientToScreen(IntPtr h, ref POINT p);
  [DllImport("user32.dll")] static extern bool PostMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] static extern bool SetCursorPos(int x, int y);
  [DllImport("user32.dll")] static extern bool SetProcessDPIAware();
  [DllImport("user32.dll")] static extern void keybd_event(byte vk, byte scan, uint flags, UIntPtr extra);
  [DllImport("user32.dll")] static extern void mouse_event(uint flags, int dx, int dy, uint data, UIntPtr extra);
  [StructLayout(LayoutKind.Sequential)] struct RECT { public int L, T, R, B; }
  [StructLayout(LayoutKind.Sequential)] struct POINT { public int X, Y; }

  static QnWin() { SetProcessDPIAware(); }

  // Una riga per finestra di primo livello del processo: hwnd|classe|titolo|visibile|ingrandita|ridotta|x,y,l,a|in primo piano
  public static string Windows(int pid) {
    var lines = new List<string>();
    IntPtr fg = GetForegroundWindow();
    EnumWindows((h, l) => {
      uint p; GetWindowThreadProcessId(h, out p);
      if (p != pid) return true;
      var t = new StringBuilder(256); GetWindowText(h, t, 256);
      var c = new StringBuilder(256); GetClassName(h, c, 256);
      RECT r; GetWindowRect(h, out r);
      POINT o = new POINT(); ClientToScreen(h, ref o);
      lines.Add(h.ToInt64() + "|" + c + "|" + t + "|" + IsWindowVisible(h) + "|" + IsZoomed(h) + "|" + IsIconic(h) + "|" + r.L + "," + r.T + "," + (r.R - r.L) + "," + (r.B - r.T) + "|" + (h == fg) + "|" + o.X + "," + o.Y);
      return true;
    }, IntPtr.Zero);
    return string.Join("\n", lines);
  }

  public static void Post(long h, uint msg, long w, long l) { PostMessage(new IntPtr(h), msg, new IntPtr(w), new IntPtr(l)); }

  [DllImport("user32.dll")] static extern bool MoveWindow(IntPtr h, int x, int y, int w, int hh, bool repaint);
  public static void Move(long h, int x, int y, int w, int hh) { MoveWindow(new IntPtr(h), x, y, w, hh, true); }

  [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint m, IntPtr w, IntPtr l);
  [DllImport("user32.dll")] static extern int GetMenuItemCount(IntPtr m);
  [DllImport("user32.dll")] static extern bool GetMenuItemRect(IntPtr h, IntPtr m, uint i, out RECT r);
  [DllImport("user32.dll", CharSet = CharSet.Unicode)] static extern int GetMenuString(IntPtr m, uint i, StringBuilder s, int n, uint flags);

  // Le voci del menu a comparsa aperto (classe #32768): testo|centro x,y in pixel dello schermo.
  public static string MenuItems(int pid) {
    var lines = new List<string>();
    EnumWindows((h, l) => {
      uint p; GetWindowThreadProcessId(h, out p);
      var c = new StringBuilder(64); GetClassName(h, c, 64);
      if (p != pid || c.ToString() != "#32768" || !IsWindowVisible(h)) return true;
      IntPtr menu = SendMessage(h, 0x01E1, IntPtr.Zero, IntPtr.Zero);
      for (uint i = 0; i < GetMenuItemCount(menu); i++) {
        var t = new StringBuilder(128); GetMenuString(menu, i, t, 128, 0x400);
        RECT r; GetMenuItemRect(IntPtr.Zero, menu, i, out r);
        lines.Add(t + "|" + ((r.L + r.R) / 2) + "," + ((r.T + r.B) / 2));
      }
      return true;
    }, IntPtr.Zero);
    return string.Join("\n", lines);
  }

  static byte Vk(string k) {
    switch (k) {
      case "ctrl": return 0x11; case "alt": return 0x12; case "shift": return 0x10;
      case "enter": return 0x0D; case "esc": return 0x1B; case "tab": return 0x09;
      case "down": return 0x28; case "up": return 0x26; case "f4": return 0x73; case "space": return 0x20;
    }
    return (byte)char.ToUpperInvariant(k[0]);
  }

  // "ctrl+alt+n": premuti in ordine, rilasciati al contrario.
  public static void Keys(string combo) {
    var ks = combo.ToLowerInvariant().Split('+');
    foreach (var k in ks) { keybd_event(Vk(k), 0, 0, UIntPtr.Zero); Thread.Sleep(15); }
    for (int i = ks.Length - 1; i >= 0; i--) { keybd_event(Vk(ks[i]), 0, 2, UIntPtr.Zero); Thread.Sleep(15); }
  }

  public static void Type(string text) { foreach (var ch in text) Keys(ch == ' ' ? "space" : ch.ToString()); }

  public static void Click(int x, int y, int count) {
    SetCursorPos(x, y); Thread.Sleep(60);
    for (int i = 0; i < count; i++) { mouse_event(2, 0, 0, 0, UIntPtr.Zero); Thread.Sleep(20); mouse_event(4, 0, 0, 0, UIntPtr.Zero); Thread.Sleep(60); }
  }

  // Trascinamento con il tasto sinistro, a piccoli passi come una mano vera.
  public static void Drag(int x1, int y1, int x2, int y2) {
    SetCursorPos(x1, y1); Thread.Sleep(80);
    mouse_event(2, 0, 0, 0, UIntPtr.Zero); Thread.Sleep(80);
    for (int i = 1; i <= 20; i++) { SetCursorPos(x1 + (x2 - x1) * i / 20, y1 + (y2 - y1) * i / 20); Thread.Sleep(25); }
    Thread.Sleep(120);
    mouse_event(4, 0, 0, 0, UIntPtr.Zero); Thread.Sleep(80);
  }
}
`;

export class Win {
  constructor() {
    this.ps = spawn('powershell.exe', ['-NoProfile', '-NonInteractive', '-Command', '-'], { stdio: ['pipe', 'pipe', 'pipe'] });
    this.buf = '';
    this.err = '';
    this.waiting = null;
    this.ps.stdout.on('data', (d) => {
      this.buf += d.toString();
      const end = this.buf.indexOf('@@FINE@@');
      if (end >= 0 && this.waiting) {
        const out = this.buf.slice(0, end).trim();
        this.buf = this.buf.slice(end + 8);
        const w = this.waiting;
        this.waiting = null;
        w(out);
      }
    });
    this.ps.stderr.on('data', (d) => (this.err += d.toString()));
    const file = join(tmpdir(), 'qn-win.cs');
    writeFileSync(file, CS);
    this.ready = this.run(`Add-Type -Path '${file}'`);
  }

  run(cmd) {
    return new Promise((resolve, reject) => {
      this.waiting = (out) => (this.err ? reject(new Error(this.err.split('\n')[0])) : resolve(out));
      this.ps.stdin.write(`${cmd}\nWrite-Output '@@FINE@@'\n`);
    });
  }

  async call(expr) {
    await this.ready;
    return this.run(expr);
  }

  async windows(pid) {
    const out = await this.call(`[QnWin]::Windows(${pid})`);
    return out.split(/\r?\n/).filter(Boolean).map((l) => {
      const [hwnd, cls, title, visible, zoomed, iconic, rect, fg, origin] = l.split('|');
      const [x, y, w, h] = rect.split(',').map(Number);
      const [ox, oy] = origin.split(',').map(Number);
      return { hwnd: Number(hwnd), cls, title, visible: visible === 'True', zoomed: zoomed === 'True', iconic: iconic === 'True', x, y, w, h, fg: fg === 'True', ox, oy };
    });
  }

  move(hwnd, x, y, w, h) {
    return this.call(`[QnWin]::Move(${hwnd}, ${x}, ${y}, ${w}, ${h})`);
  }

  async menuItems(pid) {
    const out = await this.call(`[QnWin]::MenuItems(${pid})`);
    return out.split(/\r?\n/).filter(Boolean).map((l) => {
      const [text, at] = l.split('|');
      const [x, y] = at.split(',').map(Number);
      return { text: text.split('\t')[0], x, y };
    });
  }

  keys(combo) {
    return this.call(`[QnWin]::Keys('${combo}')`);
  }

  type(text) {
    return this.call(`[QnWin]::Type('${text.replace(/'/g, "''")}')`);
  }

  post(hwnd, msg, w, l) {
    return this.call(`[QnWin]::Post(${hwnd}, ${msg}, ${w}, ${l})`);
  }

  click(x, y, count = 1) {
    return this.call(`[QnWin]::Click(${Math.round(x)}, ${Math.round(y)}, ${count})`);
  }

  drag(x1, y1, x2, y2) {
    return this.call(`[QnWin]::Drag(${Math.round(x1)}, ${Math.round(y1)}, ${Math.round(x2)}, ${Math.round(y2)})`);
  }

  close() {
    this.ps.stdin.end();
  }
}
