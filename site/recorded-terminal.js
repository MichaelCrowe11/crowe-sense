/* ============================================================================
   <recorded-terminal> - the DeepParallel signature, portable.
   Zero dependencies. Replays a recorded session in liquid glass: types the
   command, streams output with real timing, colors diffs and verdicts, then
   loops. 3D tilt on pointer move plus a slow bob. Respects reduced-motion.

   Usage (any stack):
     <recorded-terminal title="deepparallel review" badge="exit 0" badge-kind="ok">
       <script type="application/json">
         { "events": [ {"type":"cmd","text":"..."}, {"type":"out","text":"..."} ] }
       </script>
     </recorded-terminal>
   or set the session in JS:  el.session = {...}
   or load from a file:       <recorded-terminal src="/sessions/review.json">

   Event types: cmd | out | add | del | ok | warn | bad | comment | wait(ms)
   ========================================================================== */
(() => {
  if (customElements.get('recorded-terminal')) return;
  const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;
  const sleep = (ms) => new Promise(r => setTimeout(r, ms));

  const STYLE = `
    :host{display:block;perspective:1400px}
    .term{
      position:relative;border-radius:var(--r-terminal,14px);overflow:hidden;
      background:var(--glass,linear-gradient(150deg,rgba(255,255,255,.2),rgba(255,255,255,.03) 60%,rgba(210,173,98,.06)));
      -webkit-backdrop-filter:var(--blur,saturate(235%) blur(28px) brightness(1.22) contrast(1.06));
      backdrop-filter:var(--blur,saturate(235%) blur(28px) brightness(1.22) contrast(1.06));
      border:1px solid var(--gbrd,rgba(255,255,255,.2));
      box-shadow:var(--spec,inset 0 1.6px 0 0 rgba(255,255,255,.5)),0 24px 56px -28px rgba(0,0,0,.72);
      transform-style:preserve-3d;transition:transform .3s var(--ease,cubic-bezier(.16,1,.3,1));
      animation:bob 9s ease-in-out infinite;will-change:transform;
    }
    .term::before{content:"";position:absolute;inset:0;pointer-events:none;z-index:4;
      background:linear-gradient(150deg,rgba(255,255,255,.5) 0%,rgba(255,255,255,.12) 9%,transparent 24%,transparent 76%,rgba(255,255,255,.05) 92%,rgba(255,255,255,.16) 100%);
      mix-blend-mode:screen;opacity:.9}
    @keyframes bob{0%,100%{transform:translateY(0)}50%{transform:translateY(-7px)}}
    .bar{display:flex;align-items:center;gap:.6rem;padding:.7rem .9rem;border-bottom:1px solid var(--gbrd,rgba(255,255,255,.12));position:relative;z-index:5}
    .dots{display:flex;gap:.42rem}
    .dots i{width:11px;height:11px;border-radius:50%;display:block}
    .d1{background:#d9806c}.d2{background:#d8b25c}.d3{background:#87b277}
    .ttl{font:500 .76rem "JetBrains Mono",ui-monospace,monospace;color:var(--faint,#666561)}
    .badge{margin-left:auto;font:600 .64rem "JetBrains Mono",ui-monospace,monospace;letter-spacing:.08em;
      text-transform:uppercase;padding:.2rem .5rem;border-radius:999px;border:1px solid currentColor}
    .badge.ok{color:var(--ok,#8cb87c)}.badge.warn{color:var(--warn,#dcb05a)}.badge.bad{color:var(--bad,#db7c66)}
    .body{padding:1rem 1.1rem 1.2rem;font:400 .8rem/1.55 "JetBrains Mono",ui-monospace,monospace;
      color:var(--ink,#eceae4);min-height:var(--term-min,17rem);position:relative;z-index:5;
      white-space:pre-wrap;word-break:break-word}
    .ln{display:block}
    .pr{color:var(--gold,#d2ad62)}
    .add{color:#9fc890}.del{color:#d18b7e}.comment{color:var(--faint,#666561)}
    .ok{color:var(--ok,#8cb87c)}.warn{color:var(--warn,#dcb05a)}.bad{color:var(--bad,#db7c66)}
    .out{color:var(--dim,#a3a097)}
    .cursor{display:inline-block;width:.55em;height:1.05em;vertical-align:-.18em;margin-left:1px;
      background:var(--gold,#d2ad62);animation:blink 1.05s steps(1) infinite}
    @keyframes blink{50%{opacity:0}}
    @media (prefers-reduced-motion:reduce){.term{animation:none}.cursor{animation:none}}
  `;

  class RecordedTerminal extends HTMLElement {
    constructor(){ super(); this._session = null; this._stop = false; }

    connectedCallback(){
      const root = this.attachShadow({mode:'open'});
      const inline = this.querySelector('script[type="application/json"]');
      if (inline){ try{ this._session = JSON.parse(inline.textContent); }catch(e){} }
      root.innerHTML = `<style>${STYLE}</style>
        <div class="term" part="term">
          <div class="bar">
            <span class="dots"><i class="d1"></i><i class="d2"></i><i class="d3"></i></span>
            <span class="ttl"></span>
            <span class="badge"></span>
          </div>
          <div class="body"></div>
        </div>`;
      this._term = root.querySelector('.term');
      this._body = root.querySelector('.body');
      root.querySelector('.ttl').textContent = this.getAttribute('title') || '';
      const bt = this.getAttribute('badge');
      const bel = root.querySelector('.badge');
      if (bt){ bel.textContent = bt; bel.classList.add(this.getAttribute('badge-kind')||'ok'); }
      else bel.remove();

      if (!reduce) this._wireTilt();
      const start = () => { if (this._session) this._run(); };
      if (this._session) start();
      else if (this.getAttribute('src')){
        fetch(this.getAttribute('src')).then(r=>r.json()).then(s=>{this._session=s;start();}).catch(()=>{});
      }
    }
    disconnectedCallback(){ this._stop = true; }

    set session(s){ this._session = s; if (this._body) this._run(); }
    get session(){ return this._session; }

    _wireTilt(){
      const el = this._term;
      this.addEventListener('pointermove', e => {
        const r = this.getBoundingClientRect();
        const px = (e.clientX - r.left)/r.width - .5;
        const py = (e.clientY - r.top)/r.height - .5;
        el.style.transform = `rotateY(${px*7}deg) rotateX(${-py*7}deg) translateY(-2px)`;
        el.style.animationPlayState = 'paused';
      });
      this.addEventListener('pointerleave', () => {
        el.style.transform = '';
        el.style.animationPlayState = '';
      });
    }

    _line(cls){ const d=document.createElement('span'); d.className='ln '+(cls||''); this._body.appendChild(d); return d; }
    _cursor(host){ const c=document.createElement('span'); c.className='cursor'; host.appendChild(c); return c; }

    async _run(){
      this._stop = false;
      const speed = parseFloat(this.getAttribute('speed')) || 1;
      while (!this._stop){
        this._body.innerHTML = '';
        for (const ev of (this._session.events||[])){
          if (this._stop) return;
          if (ev.type === 'wait'){ await sleep((ev.ms||400)/speed); continue; }
          if (ev.type === 'cmd'){
            const line = this._line(); const pr=document.createElement('span');
            pr.className='pr'; pr.textContent=(this.getAttribute('prompt')||'❯')+' ';
            line.appendChild(pr);
            const txt=document.createElement('span'); line.appendChild(txt);
            const cur=this._cursor(line);
            if (reduce){ txt.textContent=ev.text; }
            else { for (const ch of ev.text){ if(this._stop)return; txt.textContent+=ch; await sleep((28+Math.random()*55)/speed);} }
            cur.remove();
            await sleep(360/speed);
            continue;
          }
          // output-style lines
          const cls = {out:'out',add:'add',del:'del',ok:'ok',warn:'warn',bad:'bad',comment:'comment'}[ev.type] || 'out';
          const line = this._line(cls);
          line.textContent = ev.text || '';
          await sleep((reduce?0:(ev.ms||70))/speed);
        }
        if (reduce) return;            // static for reduced motion
        await sleep(2600/speed);       // hold the finished frame, then loop
      }
    }
  }
  customElements.define('recorded-terminal', RecordedTerminal);
})();
