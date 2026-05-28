"""Format stitch maps into standard US amigurumi notation."""

import re
from collections import defaultdict

from photo_to_pattern.core.yarn_physics import YarnDynamicsEngine, YarnProfile, structural_stitch_length_mm
from photo_to_pattern.geometric_math import PatternMap, RoundSpec
from photo_to_pattern.planning.models import PlanningModel, DesignPart

from .grammar import validate_round_line
from .models import CrochetPattern, PatternSection


def _clean_name(name: str) -> str:
    # Lowercase, keep alphanumeric, strip trailing digits and underscores
    s = name.lower().strip()
    s = re.sub(r'_\d+$', '', s)
    s = re.sub(r'_\d+$', '', s)
    s = re.sub(r'\d+$', '', s)
    s = "".join(c for c in s if c.isalnum() or c == "_").strip("_")
    if s == "body":
        return "torso"
    if s.endswith("s"):
        s = s[:-1]
    return s


def find_closest_part(primitive_id: str, parts: list[DesignPart]) -> DesignPart | None:
    if not parts:
        return None
    p_clean = _clean_name(primitive_id)
    for part in parts:
        part_clean = _clean_name(part.name)
        if p_clean == part_clean:
            return part
    for part in parts:
        part_clean = _clean_name(part.name)
        if p_clean in part_clean or part_clean in p_clean:
            return part
    return None


class AssemblyBlueprintAgent:
    def format(
        self,
        pattern_map: PatternMap,
        title: str = "Photo-to-Amigurumi Pattern",
        planning_model: PlanningModel | None = None,
    ) -> CrochetPattern:
        grouped: dict[str, list[RoundSpec]] = defaultdict(list)
        for round_spec in pattern_map.rounds:
            grouped[round_spec.primitive_id].append(round_spec)

        sections: list[PatternSection] = []
        warnings = list(pattern_map.warnings)

        for primitive_id, rounds in grouped.items():
            lines = tuple(_format_round(round_spec) for round_spec in rounds)
            invalid = [line for line in lines if not validate_round_line(line)]
            if invalid:
                warnings.append(f"{primitive_id}: formatter emitted invalid notation.")
            notes = tuple(sorted({round_spec.note for round_spec in rounds if round_spec.note}))
            sections.append(
                PatternSection(
                    primitive_id=primitive_id,
                    title=f"{primitive_id.replace('_', ' ').title()}",
                    lines=lines,
                    notes=notes,
                )
            )

        final_sections: list[PatternSection] = []

        if planning_model is not None:
            # 1. Yarn & Materials Requirements
            yardages = defaultdict(float)
            yarn_engine = YarnDynamicsEngine()
            for primitive_id, rounds in grouped.items():
                part = find_closest_part(primitive_id, list(planning_model.parts))
                if part:
                    yarn_type = getattr(part, 'yarn_type', 'acrylic') or 'acrylic'
                    color_hex = getattr(part, 'color_hex', '#e87e40') or '#e87e40'
                else:
                    yarn_type = 'acrylic'
                    color_hex = '#e87e40'

                yarn_lower = yarn_type.lower().strip()
                profile = _profile_for_yarn(yarn_engine, yarn_lower, color_hex)
                yardage = sum(
                    (round_spec.stitch_count * structural_stitch_length_mm(profile, stitch_type=round_spec.action)) / 914.4
                    for round_spec in rounds
                )
                yardages[(yarn_lower, color_hex.lower().strip())] += yardage

            HEX_TO_COLOR = {
                "#e87e40": "Orange",
                "#ffffff": "White",
                "#000000": "Black",
                "#ff0000": "Red",
                "#00ff00": "Green",
                "#0000ff": "Blue",
                "#ffff00": "Yellow",
                "#808080": "Grey",
                "#a52a2a": "Brown",
                "#ffc0cb": "Pink",
                "#800080": "Purple",
            }

            sorted_yarn_lines = []
            for (y_key, c_key), yardage in sorted(yardages.items()):
                color_name = HEX_TO_COLOR.get(c_key, c_key)
                yarn_name = y_key.title() if "/" not in y_key else "Velvet/Chenille"
                sorted_yarn_lines.append(f"{yarn_name} Yarn ({color_name}): ~{yardage:.1f} yards")

            body_yarn_type = "acrylic"
            body_part = None
            for p_id in grouped.keys():
                if "body" in p_id.lower() or "torso" in p_id.lower():
                    body_part = find_closest_part(p_id, list(planning_model.parts))
                    if body_part:
                        break
            if not body_part and planning_model.parts:
                for part in planning_model.parts:
                    if "body" in part.name.lower() or "torso" in part.name.lower():
                        body_part = part
                        break
            if not body_part and planning_model.parts:
                body_part = planning_model.parts[0]

            if body_part:
                body_yarn_type = getattr(body_part, 'yarn_type', 'acrylic') or 'acrylic'

            hook_size = "3.25 mm (US D-3) to 3.75 mm (US F-5)"
            b_yarn_lower = body_yarn_type.lower().strip()
            if b_yarn_lower == "cotton":
                hook_size = "2.25 mm (US B-1) to 2.75 mm (US C-2)"
            elif b_yarn_lower == "wool":
                hook_size = "3.5 mm (US E-4) to 4.0 mm (US G-6)"
            elif b_yarn_lower == "velvet/chenille":
                hook_size = "5.0 mm (US H-8) to 6.0 mm (US J-10)"

            target_height = getattr(planning_model.options, 'target_height_inches', 8.0)
            infant_safe = getattr(planning_model.options, 'infant_safe', False)
            eye_size_mm = max(6, min(24, round(target_height * 1.5)))
            eye_line = f"Safety eyes: {eye_size_mm} mm"
            if infant_safe:
                eye_line += " (Choking hazard: Since Child Safety Mode is enabled, replace plastic eyes with embroidered eyes or soft felt circles!)"

            materials_lines = [
                f"Crochet Hook: {hook_size}",
            ]
            materials_lines.extend(sorted_yarn_lines)
            materials_lines.extend([
                eye_line,
                "Fiberfill stuffing",
                "Tapestry needle",
            ])

            materials_section = PatternSection(
                primitive_id="yarn_materials_requirements",
                title="Yarn & Materials Requirements",
                lines=tuple(materials_lines),
                notes=(),
            )
            final_sections.append(materials_section)

            # 2. Stitch Abbreviations Key
            abbrev_section = PatternSection(
                primitive_id="stitch_abbreviations_key",
                title="Stitch Abbreviations Key",
                lines=(
                    "MR: Magic Ring",
                    "sc: single crochet",
                    "inc: increase",
                    "inv dec: invisible decrease",
                    "sl st: slip stitch",
                    "ch: chain",
                ),
                notes=(),
            )
            final_sections.append(abbrev_section)

        final_sections.extend(sections)

        if planning_model is not None:
            # 3. Assembly & Sewing Instructions
            head_rounds = []
            for p_id, rds in grouped.items():
                if p_id.lower() == "head":
                    head_rounds = rds
                    break
            if not head_rounds:
                for p_id, rds in grouped.items():
                    if "head" in p_id.lower():
                        head_rounds = rds
                        break

            N = len(head_rounds)
            if N > 0:
                mid = round(N * 0.6)
                round_a = max(1, mid - 1)
                round_b = min(N, mid + 1)
            else:
                round_a = 12
                round_b = 14

            # Calculate dynamic eye placement gap and style-aware interpupillary stitch gaps
            eye_gap = 8
            style = ""
            if planning_model and planning_model.options:
                style = (planning_model.options.aesthetic_style or "classic").lower().strip()
                if "chibi" in style:
                    eye_gap = 10
                elif "kawaii" in style:
                    eye_gap = 12

            drift_shift = max(1, round(round_a / 4))
            if "chibi" in style or "kawaii" in style:
                eye_placement_str = f"2. Eye Placement: Place safety eyes between Rounds {round_a} and {round_b} (about 60% down the Head), about {eye_gap} stitches apart (interpupillary stitch gap for custom aesthetic). (To compensate for the 3.5-degree spiral drift factor, shift the left eye backward by {drift_shift} stitch index to remain perfectly anatomically centered.)"
            else:
                eye_placement_str = f"2. Eye Placement: Place safety eyes between Rounds {round_a} and {round_b} (about 60% down the Head), about 8 stitches apart. (To compensate for the 3.5-degree spiral drift factor, shift the left eye backward by {drift_shift} stitch index to remain perfectly anatomically centered.)"

            assembly_lines = (
                "1. Stuffing: Stuff the Head and Torso firmly with fiberfill stuffing before closing.",
                eye_placement_str,
                "3. Limb Anchor matrices (Assembly Seam Coordinates):",
                "   - Torso to Head: Sew Torso centered to Head neck line.",
                "   - Ears to Head: Sew symmetrically on both sides between Rounds 4 and 8.",
                "   - Muzzle/Snout: Sew centered on lower front face between Rounds 14 and 18.",
                "   - Arms to Torso: Sew to upper sides near Rounds 5-7.",
                "   - Legs to Torso: Sew to lower sides/bottom near Rounds 18-20.",
                "   - Tail to Torso: Sew centered at lower back near Rounds 16-18.",
            )

            assembly_section = PatternSection(
                primitive_id="assembly_sewing_instructions",
                title="Assembly & Sewing Instructions",
                lines=assembly_lines,
                notes=(),
            )
            final_sections.append(assembly_section)

        return CrochetPattern(
            title=title,
            stitch_style="Spiral rounds",
            terminology="US crochet",
            sections=tuple(final_sections),
            warnings=tuple(warnings),
        )


class PatternFormatter(AssemblyBlueprintAgent):
    """Backward-compatible name for the AssemblyBlueprintAgent."""


def _profile_for_yarn(engine: YarnDynamicsEngine, yarn_lower: str, color_hex: str) -> YarnProfile:
    if yarn_lower == "cotton":
        return engine.profile(weight=2, hook_mm=2.5, fiber="cotton", color_hex=color_hex)
    if yarn_lower == "wool":
        return engine.profile(weight=4, hook_mm=3.75, fiber="wool", color_hex=color_hex)
    if yarn_lower == "velvet/chenille":
        return engine.profile(weight=6, hook_mm=5.5, fiber="chenille", color_hex=color_hex)
    return engine.profile(weight=4, hook_mm=3.5, fiber="acrylic", color_hex=color_hex)


def _format_round(round_spec: RoundSpec) -> str:
    if "flat panel" in round_spec.note.lower():
        prefix = f"Row {round_spec.round_number}:"
        return f"{prefix} Ch {round_spec.stitch_count + 1}, Sc across ({round_spec.stitch_count} sts)"

    prefix = f"R{round_spec.round_number}:"
    count = f"({round_spec.stitch_count} sts)"

    if round_spec.action == "mr":
        return f"{prefix} MR, {round_spec.stitch_count} Sc {count}"
    if round_spec.action == "even":
        return f"{prefix} Sc around {count}"
    if round_spec.action == "inc":
        body = _format_operation_round(round_spec.previous_stitch_count, round_spec.delta, "Inc")
        return f"{prefix} {body} {count}"
    body = _format_operation_round(round_spec.previous_stitch_count, abs(round_spec.delta), "Inv Dec")
    return f"{prefix} {body} {count}"


def _format_operation_round(previous_count: int, operations: int, op_token: str) -> str:
    if operations <= 0:
        return "Sc around"
    if previous_count <= operations:
        return f"{op_token} around"

    if previous_count % operations == 0:
        sc_between = max(0, previous_count // operations - (2 if op_token == "Inv Dec" else 1))
        if sc_between <= 0:
            return f"({op_token}) x {operations}"
        return f"({sc_between} Sc, {op_token}) x {operations}"

    base = max(1, previous_count // operations)
    return f"Stagger {operations} {op_token} evenly, about every {base} stitches"
