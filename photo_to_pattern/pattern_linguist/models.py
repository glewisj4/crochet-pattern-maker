"""Pattern text models."""

from dataclasses import dataclass


@dataclass(frozen=True)
class PatternSection:
    primitive_id: str
    title: str
    lines: tuple[str, ...]
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrochetPattern:
    title: str
    stitch_style: str
    terminology: str
    sections: tuple[PatternSection, ...]
    warnings: tuple[str, ...] = ()

    def render(self) -> str:
        parts = [
            self.title,
            "",
            f"Style: {self.stitch_style}",
            f"Terminology: {self.terminology}",
            "",
            "Abbreviations: MR = magic ring, Sc = single crochet, Inc = 2 sc in next stitch, Inv Dec = invisible decrease.",
        ]
        if self.warnings:
            parts.extend(["", "Review before crocheting:"])
            parts.extend(f"- {warning}" for warning in self.warnings)

        for section in self.sections:
            parts.extend(["", section.title])
            parts.extend(section.lines)
            if section.notes:
                parts.extend(f"Note: {note}" for note in section.notes)

        return "\n".join(parts)

