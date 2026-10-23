"""Optional read-only HTTP evidence capture; never edits or uploads to the Wiki."""
import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from paths import ROOT

def fetch(url):
    with urlopen(Request(url, headers={'User-Agent': 'WTWikiOfflineValidation/1.0'}), timeout=60) as response:
        return response.read().decode('utf-8')

def main():
    for slug, title in [('china-aviation', '中国空军'), ('germany-boats', '德国近岸海军')]:
        url='https://wiki.biligame.com/warthunder/api.php?'+urlencode({'action':'parse','page':title,'prop':'text|wikitext|images','format':'json'})
        result=json.loads(fetch(url))
        (ROOT/'evidence'/('bwiki-'+slug+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
        print(title, result.get('error') or result['parse']['title'])
    for branch in ('aviation','fleet'):
        try:source=fetch('https://wiki.warthunder.com/'+branch)
        except Exception as error:
            print('official evidence unavailable',branch,str(error));continue
        (ROOT/'evidence'/('official-'+branch+'.html')).write_text(source,encoding='utf-8')
        print('official',branch,len(source))

if __name__=='__main__': main()
