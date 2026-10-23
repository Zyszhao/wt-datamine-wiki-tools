"""Public encyclopaedia tree policy; preserve raw catalogue records separately."""
GAME_TYPES = {
    'typeLightTank': '轻型坦克', 'typeMediumTank': '中型坦克',
    'typeHeavyTank': '重型坦克', 'typeTankDestroyer': '坦克歼击车',
    'typeSPAA': '自行防空炮',
}
TAG_TYPES = {
    'type_light_tank': 'typeLightTank', 'type_medium_tank': 'typeMediumTank',
    'type_heavy_tank': 'typeHeavyTank', 'type_tank_destroyer': 'typeTankDestroyer',
    'type_spaa': 'typeSPAA',
}
# No general event marker exists for this racing clone in the inspected tags.
# Explicit scope decision: racing variant, not the obtainable Black Cat vehicle.
SPECIAL_VARIANTS = {
    'us_m18_hellcat_black_cat_race': 'special racing variant; units.csv English shop name: "Racing" M18',
    # Explicit game-code policy, not a blanket ban on obtainable event rewards.
    # These shop entries are hidden mission/race/WWI-mode clones; the normal
    # obtainable counterparts remain in the encyclopaedia trees and full index.
    'cn_ztz_96a_race': 'special racing variant of cn_ztz_96a',
    'ussr_t_80u_race': 'special racing variant of ussr_t_80u',
    'ussr_pr_206_race': 'special racing variant of ussr_pr_206',
    'f_4e_event': 'mission/event-only clone of f-4e',
    'mig-21_bis_event': 'mission/event-only clone of mig-21_bis',
    'os2u_1_naval': 'ship-launched mission aircraft clone of os2u_1',
    'germ_garford_putilov_event': 'WWI special-mode vehicle, not a research/reward vehicle',
    'germ_beutepanzer_mk_iv_event': 'WWI special-mode vehicle, not a research/reward vehicle',
    'germ_a7v_event': 'WWI special-mode vehicle, not a research/reward vehicle',
    'uk_garford_putilov_event': 'WWI special-mode vehicle, not a research/reward vehicle',
    'uk_saint_chamond_event': 'WWI special-mode vehicle, not a research/reward vehicle',
    'uk_mark_v_event': 'WWI special-mode vehicle, not a research/reward vehicle',
}

def exclusion_reason(code, unit_tags):
    tags = unit_tags.get(code, {})
    if tags.get('operatorCountry') == 'country_invisible':
        return 'unittags.operatorCountry=country_invisible'
    if tags.get('tags', {}).get('hideBrForVehicle'):
        return 'unittags.tags.hideBrForVehicle=true'
    return SPECIAL_VARIANTS.get(code)

def game_type(unit_tags, model_type=None):
    found = [target for key, target in TAG_TYPES.items() if unit_tags.get('tags', {}).get(key)]
    if len(found) == 1:
        return found[0], 'unittags.tags'
    if isinstance(model_type, list) and len(set(model_type)) == 1:
        model_type = model_type[0]
    if isinstance(model_type, str) and model_type in GAME_TYPES:
        return model_type, 'tankmodels.type'
    return None, 'unresolved'
