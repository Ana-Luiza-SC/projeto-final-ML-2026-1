from __future__ import annotations
import re
from dataclasses import dataclass

DAYS = {"2": "Segunda-feira", "3": "Terça-feira", "4": "Quarta-feira", "5": "Quinta-feira", "6": "Sexta-feira", "7": "Sábado"}
SLOTS = {"M1": ("08:00", "08:55"), "M2": ("08:55", "09:50"), "M3": ("10:00", "10:55"), "M4": ("10:55", "11:50"), "T2": ("14:00", "14:55"), "T3": ("14:55", "15:50"), "T4": ("16:00", "16:55"), "T5": ("16:55", "17:50"), "T6": ("18:00", "18:55"), "N1": ("19:00", "19:50"), "N2": ("19:50", "20:40"), "N3": ("20:50", "21:40"), "N4": ("21:40", "22:30")}

@dataclass(frozen=True)
class Slot:
    day: str; start_time: str; end_time: str; source: str
    def dump(self): return {"day": self.day, "start_time": self.start_time, "end_time": self.end_time, "source": self.source}

def merge(slots: list[Slot]) -> list[Slot]:
    result: list[Slot] = []
    for slot in sorted(slots, key=lambda x: (list(DAYS.values()).index(x.day), x.start_time)):
        if result and result[-1].day == slot.day and result[-1].end_time == slot.start_time and result[-1].source == slot.source:
            result[-1] = Slot(slot.day, result[-1].start_time, slot.end_time, slot.source)
        else: result.append(slot)
    return result

def decode(code: str | None) -> list[Slot]:
    result = []
    for days, shift, indexes in re.findall(r"([2-7]+)([MTN])([1-6]+)", (code or "").upper()):
        if any(shift + index not in SLOTS for index in indexes): continue
        for day in days:
            for index in indexes:
                start, end = SLOTS[shift + index]; result.append(Slot(DAYS[day], start, end, "decoded_code"))
    return merge(result)

def from_weekly_table(table, codes: set[str]) -> dict[str, list[Slot]]:
    aliases = {"seg": "Segunda-feira", "ter": "Terça-feira", "qua": "Quarta-feira", "qui": "Quinta-feira", "sex": "Sexta-feira", "sab": "Sábado"}
    if len(table) < 2: return {}
    columns = {i: day for i, value in enumerate(table[0]) for key, day in aliases.items() if str(value or "").casefold().startswith(key)}
    found: dict[str, list[Slot]] = {}
    for row in table[1:]:
        times = re.findall(r"\d{2}:\d{2}", str(row[0] or ""))
        if len(times) != 2: continue
        for column, day in columns.items():
            value = str(row[column] or "").upper() if column < len(row) else ""
            for code in codes:
                if code in value: found.setdefault(code, []).append(Slot(day, times[0], times[1], "receipt_table"))
    return {code: merge(slots) for code, slots in found.items()}

def resolve(code: str | None, explicit: list[Slot] | None = None):
    decoded = decode(code); chosen = explicit or decoded
    source = "receipt_table" if explicit else ("decoded_code" if decoded else "unresolved")
    warnings = []
    if explicit and decoded and [(x.day,x.start_time,x.end_time) for x in explicit] != [(x.day,x.start_time,x.end_time) for x in decoded]: warnings.append("Tabela semanal priorizada por divergir do código compacto.")
    if not chosen: warnings.append("Horário não interpretado; revise manualmente.")
    display = "; ".join(f"{x.day}, {x.start_time}–{x.end_time}" for x in chosen) or None
    return [x.dump() for x in chosen], display, source, warnings
