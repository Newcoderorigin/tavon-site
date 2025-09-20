// 4D: background stars (time-parallax)
const c = document.getElementById('stars'), x = c.getContext('2d');
function resize(){ c.width = innerWidth; c.height = innerHeight }
addEventListener('resize', resize); resize();
const S = Array.from({length:200},()=>({x:Math.random()*c.width,y:Math.random()*c.height,z:Math.random()*2+0.5}));
function draw(){
  x.clearRect(0,0,c.width,c.height);
  const t = Date.now()/1000;
  for(const s of S){
    const off = Math.sin((s.x+s.y+t)*0.05)*s.z*0.8;
    x.fillStyle = `rgba(124,155,255,${0.6+s.z*0.2})`;
    x.fillRect(s.x+off, s.y+off, s.z, s.z);
  }
  requestAnimationFrame(draw);
} draw();

// Clock
const clk = document.getElementById('clock');
function tick(){ clk.textContent = new Date().toLocaleString(); requestAnimationFrame(()=>{}) }
setInterval(tick, 1000); tick();

// 4D Memory (local, private)
const TL_KEY = 'tavon.timeline';
function addTL(evt, data){ const arr = JSON.parse(localStorage.getItem(TL_KEY)||'[]'); arr.unshift({t:Date.now(), evt, data}); localStorage.setItem(TL_KEY, JSON.stringify(arr.slice(0,25))); renderTL(); }
function renderTL(){
  const el = document.getElementById('timeline'); if(!el) return;
  const arr = JSON.parse(localStorage.getItem(TL_KEY)||'[]');
  el.innerHTML = arr.map(i=>`<li><strong>${i.evt}</strong> — ${new Date(i.t).toLocaleString()}<br><span class="small muted">${JSON.stringify(i.data)}</span></li>`).join('');
}
renderTL();

// Theme prefs
const themeSel = document.getElementById('themeSel'), saveMsg = document.getElementById('saveMsg');
const THEME_KEY = 'tavon.theme';
function applyTheme(v){ document.documentElement.classList.remove('theme-onyx','theme-sunset'); if(v!=='nebula'){ document.documentElement.classList.add('theme-'+v); } }
applyTheme(localStorage.getItem(THEME_KEY)||'nebula');
themeSel.value = localStorage.getItem(THEME_KEY)||'nebula';
document.getElementById('savePref').onclick = () => {
  localStorage.setItem(THEME_KEY, themeSel.value); applyTheme(themeSel.value);
  addTL('pref:theme', {theme: themeSel.value}); saveMsg.textContent = 'saved';
  setTimeout(()=>saveMsg.textContent='', 1200);
};

// Contact (private demo)
document.getElementById('contactForm').addEventListener('submit', e=>{
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target).entries());
  localStorage.setItem('contact.last', JSON.stringify(data));
  addTL('contact:draft', {name:data.name, email:data.email});
  alert('Saved locally. Wire to your backend when ready.');
});

// Modal
function openModal(kind){
  const mc = document.getElementById('modalContent');
  mc.innerHTML = ({
    trend:`<h3>Affiliate Trend Finder</h3><p>Command-line builder that generates a static site + social CSV with your Amazon tag. Docker-friendly.</p>`,
    align:`<h3>AlignmentForge</h3><p>Intent→Forks→Rituals with local audit trail. Private by default.</p>`,
    sri:`<h3>SRI Sandbox</h3><p>Explore nearby-possible worlds (simulation only) to prototype choices.</p>`
  })[kind] || '<p>…</p>';
  document.getElementById('modal').classList.add('show');
  addTL('modal:open', {kind});
}
function closeModal(){ document.getElementById('modal').classList.remove('show'); }
window.openModal=openModal; window.closeModal=closeModal;

// Footer year
document.getElementById('y').textContent = new Date().getFullYear();
