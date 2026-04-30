from architect.prompt_director import PromptDirectorResult, enhance_prompt


def test_prompt_director_result_preserves_raw_prompt_and_reference_terms() -> None:
    result = PromptDirectorResult.model_validate(
        {
            "raw_prompt": "a staff that shoots gojo's hollow purple from jjk",
            "enhanced_prompt": (
                "a forbidden staff that charges a slow black-violet singularity, "
                "pulls enemies inward, tears space behind it, then collapses into "
                "a huge hollow-purple shockwave"
            ),
            "protected_reference_terms": ["gojo", "hollow purple", "jjk"],
            "reference_subject": "Gojo Hollow Purple from JJK",
            "mechanics_intent": "charged singularity projectile with gravity pull",
            "spectacle_intent": "black-violet spatial distortion and shockwave",
        }
    )

    assert result.raw_prompt.startswith("a staff")
    assert "gojo" in result.protected_reference_terms
    assert "hollow-purple shockwave" in result.enhanced_prompt


def test_prompt_director_result_falls_back_to_raw_prompt_when_enhanced_blank() -> None:
    result = PromptDirectorResult.model_validate(
        {
            "raw_prompt": "a strange mirror staff",
            "enhanced_prompt": "   ",
        }
    )

    assert result.enhanced_prompt == "a strange mirror staff"


def test_enhance_prompt_expands_hollow_purple_without_dropping_reference_terms() -> None:
    result = enhance_prompt(
        "a staff that shoots gojo's hollow purple from jjk",
        tier="Tier3_Hardmode",
    )

    assert result.raw_prompt == "a staff that shoots gojo's hollow purple from jjk"
    assert "gojo" in result.protected_reference_terms
    assert "hollow purple" in result.protected_reference_terms
    assert "jjk" in result.protected_reference_terms
    assert result.reference_slots["projectile"].subject == "Gojo Hollow Purple from JJK"
    assert result.reference_slots.projectile.subject == "Gojo Hollow Purple from JJK"
    assert "hollow purple" in result.reference_slots.projectile.protected_terms
    assert "charges" in result.enhanced_prompt
    assert "singularity" in result.enhanced_prompt
    assert "shockwave" in result.enhanced_prompt


def test_enhance_prompt_preserves_common_reference_variants() -> None:
    result = enhance_prompt(
        "a staff that shoots Gojo's hollow-purple from Jujutsu Kaisen",
        tier="Tier3_Hardmode",
    )

    assert result.protected_reference_terms == ["gojo", "hollow purple", "jjk"]
    assert result.reference_slots.projectile.protected_terms == [
        "gojo",
        "hollow purple",
        "jjk",
    ]


def test_enhance_prompt_does_not_turn_gojo_alone_into_hollow_purple() -> None:
    raw_prompt = "a gojo blindfold staff"
    result = enhance_prompt(raw_prompt, tier="Tier3_Hardmode")

    assert result.enhanced_prompt == raw_prompt
    assert result.reference_slots.projectile.subject == ""
