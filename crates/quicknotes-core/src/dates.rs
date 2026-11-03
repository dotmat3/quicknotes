//! Date in italiano: titoli, etichette e gruppi delle scadenze. Funzioni pure.

use chrono::{Datelike, Days, NaiveDate, Weekday};
use serde::Serialize;

const MONTHS: [&str; 12] = ["gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic"];
const MONTHS_FULL: [&str; 12] = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto", "settembre", "ottobre",
    "novembre", "dicembre",
];

fn weekday_full(d: NaiveDate) -> &'static str {
    match d.weekday() {
        Weekday::Mon => "Lunedì",
        Weekday::Tue => "Martedì",
        Weekday::Wed => "Mercoledì",
        Weekday::Thu => "Giovedì",
        Weekday::Fri => "Venerdì",
        Weekday::Sat => "Sabato",
        Weekday::Sun => "Domenica",
    }
}

fn weekday_short(d: NaiveDate) -> &'static str {
    match d.weekday() {
        Weekday::Mon => "lun",
        Weekday::Tue => "mar",
        Weekday::Wed => "mer",
        Weekday::Thu => "gio",
        Weekday::Fri => "ven",
        Weekday::Sat => "sab",
        Weekday::Sun => "dom",
    }
}

pub fn parse_day(value: &str) -> Option<NaiveDate> {
    NaiveDate::parse_from_str(value.get(..10)?, "%Y-%m-%d").ok()
}

/// Il titolo a schermo della nota del giorno: "Domenica 1 novembre".
pub fn daily_title(d: NaiveDate) -> String {
    format!("{} {} {}", weekday_full(d), d.day(), MONTHS_FULL[d.month0() as usize])
}

/// Il titolo nel file della nota del giorno, uguale a quello delle note già esistenti.
pub fn daily_file_title(d: NaiveDate) -> String {
    format!("Giornata di {} {}", weekday_full(d).to_lowercase(), d.format("%d/%m/%Y"))
}

/// "2 nov".
pub fn short_day(d: NaiveDate) -> String {
    format!("{} {}", d.day(), MONTHS[d.month0() as usize])
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum DueLevel {
    Late,
    Soon,
    Normal,
}

/// Etichetta di una scadenza: "30 ott" se è passata, "oggi", "domani", altrimenti "lun 2 nov".
pub fn due_label(due: NaiveDate, today: NaiveDate) -> (String, DueLevel) {
    let days = (due - today).num_days();
    match days {
        d if d < 0 => (short_day(due), DueLevel::Late),
        0 => ("oggi".to_string(), DueLevel::Soon),
        1 => ("domani".to_string(), DueLevel::Soon),
        _ => (format!("{} {}", weekday_short(due), short_day(due)), DueLevel::Normal),
    }
}

/// Colonna della bacheca a cui appartiene una scadenza.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "lowercase")]
pub enum DueGroup {
    Late,
    Soon,
    Week,
    Later,
    None,
}

/// "Oggi e domani", poi "Questa settimana" fino a domenica, poi "Più avanti".
pub fn due_group(due: Option<NaiveDate>, today: NaiveDate) -> DueGroup {
    let Some(due) = due else { return DueGroup::None };
    let days = (due - today).num_days();
    if days < 0 {
        return DueGroup::Late;
    }
    if days <= 1 {
        return DueGroup::Soon;
    }
    let to_sunday = 6 - u64::from(today.weekday().num_days_from_monday());
    match today.checked_add_days(Days::new(to_sunday)) {
        Some(sunday) if due <= sunday => DueGroup::Week,
        _ => DueGroup::Later,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn d(s: &str) -> NaiveDate {
        parse_day(s).unwrap()
    }

    #[test]
    fn titoli() {
        assert_eq!(daily_title(d("2026-11-01")), "Domenica 1 novembre");
        assert_eq!(daily_file_title(d("2026-11-01")), "Giornata di domenica 01/11/2026");
    }

    #[test]
    fn etichette() {
        let t = d("2026-11-01");
        assert_eq!(due_label(d("2026-10-30"), t), ("30 ott".into(), DueLevel::Late));
        assert_eq!(due_label(t, t), ("oggi".into(), DueLevel::Soon));
        assert_eq!(due_label(d("2026-11-02"), t), ("domani".into(), DueLevel::Soon));
        assert_eq!(due_label(d("2026-11-04"), t), ("mer 4 nov".into(), DueLevel::Normal));
    }

    #[test]
    fn gruppi_di_domenica_e_a_cavallo_della_settimana() {
        let sunday = d("2026-11-01");
        assert_eq!(due_group(Some(d("2026-11-02")), sunday), DueGroup::Soon);
        assert_eq!(due_group(Some(d("2026-11-03")), sunday), DueGroup::Later, "di domenica la settimana è finita");
        let monday = d("2026-11-02");
        assert_eq!(due_group(Some(d("2026-11-08")), monday), DueGroup::Week);
        assert_eq!(due_group(Some(d("2026-11-09")), monday), DueGroup::Later);
        assert_eq!(due_group(Some(d("2026-11-01")), monday), DueGroup::Late);
        assert_eq!(due_group(None, monday), DueGroup::None);
        let friday = d("2026-12-25");
        assert_eq!(due_group(Some(d("2027-01-01")), friday), DueGroup::Later);
    }
}
