# Vienna collection search

On 2026-11-25 the coordinator searched DIVINA, the Natural History Museum Vienna's public catalog. The question was whether the published interface could identify a specimen from the two Pola stations. Each query used the Mollusca collection filter. [DIVINA search](https://divina.nhm.at/search)

| Search text | Records returned | Interpretation |
|---|---:|---|
| Empty | 199 | Size of the searchable public subset on this date |
| Helix | 1 | Positive control for this form and filter. [Returned object](https://divina.nhm.at/object/NHMW-ZOO-MO-0081100-ETH-043) |
| Pterotrachea | 0 | No indexed genus-text match in the subset |
| Pola | 0 | No indexed expedition-text match in the subset |

Reproduce by opening Search, choosing **Mollusca collection**, and entering each term. The same public form accepts these parameters.

```sh
curl -fsSL --data-urlencode 'collections[]=15' --data-urlencode 'searchtext=Pterotrachea' https://divina.nhm.at/search
```

Vienna holds material from the Pola expeditions, and an Austrian collection inventory estimates around one million mollusk lots. The 199 public search entries provide little coverage of those holdings. The original marine collection register or lot labels could still tie specimens to the expedition, station, date and historical name. Until then the publication supports a literature occurrence and any specimen accession remains unresolved. [NHMW Pola material study](https://pmc.ncbi.nlm.nih.gov/articles/PMC6225989/) · [Collection inventory](https://forschungsinfrastruktur.bmfwf.gv.at/en/cluster/dissco-at-distributed-system-of-scientific-collections-austria_6?id=4562)
