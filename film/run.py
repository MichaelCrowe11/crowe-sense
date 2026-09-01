"""Fan-out: assemble every film in parallel once the voice manifest exists. Writes out/manifest.json."""
import json, os, sys, time
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from targets import all_scripts
import assemble
def one(film):
    man = json.load(open(os.path.join(HERE, "out", "voice", "manifest.json")))
    try: return assemble.build(film, man)
    except Exception as e: return dict(slug=film["slug"], error=str(e)[:400])
if __name__ == "__main__":
    films = all_scripts(); t0 = time.time()
    # the shared spine cards and clips must exist before the fan-out, so build the first film alone
    first = one(films[0]); print(json.dumps(first), flush=True)
    results = [first]
    with ProcessPoolExecutor(max_workers=int(sys.argv[1]) if len(sys.argv) > 1 else 6) as ex:
        for r in ex.map(one, films[1:]): print(json.dumps(r), flush=True); results.append(r)
    json.dump(results, open(os.path.join(HERE, "out", "manifest.json"), "w"), indent=1)
    ok = [r for r in results if "master" in r]
    print(f"{len(ok)}/{len(results)} films in {round(time.time()-t0)}s; {sum(r['seconds'] for r in ok)/60:.1f} min total runtime", flush=True)
