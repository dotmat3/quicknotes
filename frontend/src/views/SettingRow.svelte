<script>
  let { label, desc = '', children } = $props();
</script>

<div class="row">
  <div class="text"><div class="label">{label}</div>{#if desc}<div class="desc">{desc}</div>{/if}</div>
  {@render children()}
</div>

<style>
  .row { display: flex; flex-wrap: wrap; align-items: center; gap: 10px 16px; padding: 14px 16px; }
  .text { flex: 1 1 240px; min-width: 0; }
  .label { font-size: 14px; color: var(--text); }
  .desc { font-size: 12.5px; line-height: 1.45; color: var(--subtle); }
</style>
