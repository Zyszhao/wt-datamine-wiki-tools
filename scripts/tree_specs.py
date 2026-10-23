"""Data selection only; every tree uses the same converter, Lua and browser script."""
COUNTRIES = {'usa':'美国','germany':'德国','ussr':'苏联','britain':'英国','japan':'日本','china':'中国','italy':'意大利','france':'法国','sweden':'瑞典','israel':'以色列'}
BRANCHES = {'army':'陆战','aviation':'空军','helicopters':'直升机','ships':'远洋海军','boats':'近岸海军'}
DEPLOY_TREES = ('usa_army', 'china_aviation', 'germany_boats')
BRANCH_CLASSES = {
    'army': {'exp_tank','exp_heavy_tank','exp_tank_destroyer','exp_SPAA'},
    'aviation': {'exp_fighter','exp_assault','exp_bomber'},
    'helicopters': {'exp_helicopter'},
    'ships': {'exp_destroyer','exp_cruiser'},
    'boats': {'exp_torpedo_boat','exp_gun_boat','exp_torpedo_gun_boat','exp_submarine_chaser','exp_naval_ferry_barge'},
}

def tree_id(country, branch): return country.removeprefix('country_')+'_'+branch
def tree_label(country, branch): return COUNTRIES[country.removeprefix('country_')]+BRANCHES[branch]
