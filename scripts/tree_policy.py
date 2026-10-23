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
