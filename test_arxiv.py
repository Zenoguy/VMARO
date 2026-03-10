import requests
import xml.etree.ElementTree as ET

topic = "AI in High frequency trading"
query_terms = [w for w in topic.split() if w.lower() not in ('in', 'on', 'the', 'of', 'and', 'a', 'to', 'for')]
query3 = '+AND+'.join([f'all:{w}' for w in query_terms])

# We should not URL-encode AND spaces ourselves if passing via params, because requests does it.
# Actually arXiv specifically wants `+AND+` in the raw string, or `%2BAND%2B`.
# If we pass search_query="all:AI AND all:High AND all:frequency AND all:trading"
query4 = ' AND '.join([f'all:{w}' for w in query_terms])

def test(query):
    params = {"search_query": query, "max_results": 2}
    r = requests.get("http://export.arxiv.org/api/query", params=params)
    print("URL:", r.url)
    root = ET.fromstring(r.text)
    ns = {'atom': 'http://www.w3.org/2005/Atom'}
    titles = [entry.find('atom:title', ns).text.strip().replace('\n', ' ') for entry in root.findall('atom:entry', ns)]
    print(titles)

test(query3)
test(query4)
test(f'all:{topic}') # the original un-fixed logic
