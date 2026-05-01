from core.workshop_director import build_variants


def test_build_variants_returns_two_or_three_materialized_variants() -> None:
    variants = build_variants(
        bench_manifest={"item_name": "Storm Brand"},
        directive="make the projectile feel heavier",
    )

    assert 2 <= len(variants) <= 3
    assert all("variant_id" in variant for variant in variants)
    assert all("label" in variant for variant in variants)
    assert all("manifest" in variant for variant in variants)
