"""Fan-out for the footage cut: first film alone (renders the shared spine), then the rest in parallel."""
import json, os, sys, time
from concurrent.futures import ProcessPoolExecutor
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from targets import all_scripts
import assemble2
def one(film):
    man = json.load(open(os.path.join(HERE, os.environ.get("VOICE_DIR", "out/voice"), "manifest.json"))); shots = json.load(open(os.path.join(HERE, "shotlist.json")))
    try: return assemble2.build(film, man, shots)
    except Exception as e: return dict(slug=film["slug"], error=str(e)[:400])
if __name__ == "__main__":
    films = all_scripts(); t0 = time.time(); results = [one(films[0])]; print(json.dumps(results[0]), flush=True)
    with ProcessPoolExecutor(max_workers=int(sys.argv[1]) if len(sys.argv) > 1 else 5) as ex:
        for r in ex.map(one, films[1:]): print(json.dumps(r), flush=True); results.append(r)
    json.dump(results, open(os.path.join(HERE, "out2", "manifest.json"), "w"), indent=1)
    ok = [r for r in results if "master" in r]; print(f"{len(ok)}/{len(results)} films in {round(time.time()-t0)}s", flush=True)
