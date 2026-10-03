/* Dimensionless inertial Langevin model. Usable offline and in Node tests. */
(function (root) {
  'use strict';
  const defaults = Object.freeze({ D: 0.22, f: 0.18, omega: 0.04, gamma: 1, dt: 0.02, seed: 42 });
  const limits = {D:[0,1.5], f:[0,0.5], omega:[0.02,0.2], gamma:[0.3,3], dt:[0.005,0.04], seed:[0,4294967295]};
  function validate(p) {
    for (const [k,[lo,hi]] of Object.entries(limits)) if (!Number.isFinite(p[k]) || p[k]<lo || p[k]>hi) throw new RangeError(k);
    if (!Number.isInteger(p.seed)) throw new RangeError('seed');
    return p;
  }
  class Random {
    constructor(seed) { this.state=seed>>>0; }
    uniform() { let t=this.state=(this.state+0x6D2B79F5)>>>0; t=Math.imul(t^(t>>>15),t|1); t^=t+Math.imul(t^(t>>>7),t|61); return ((t^(t>>>14))>>>0)/4294967296; }
    normal() { return Math.sqrt(-2*Math.log(1-this.uniform()))*Math.cos(2*Math.PI*this.uniform()); }
  }
  const potential = x => -x*x/2+x**4/8;
  const force = (x,t,p) => x-x**3/2+p.f*Math.sin(p.omega*t);
  class Model {
    constructor(p={}) {
      this.p=validate({...defaults,...p}); this.random=new Random(this.p.seed);
      this.t=0; this.x=-Math.SQRT2; this.v=0; this.steps=0; this.transitions=0; this.well=-1; this.lastTransition=null; this.residences=[];
      this.decay=Math.exp(-this.p.gamma*this.p.dt);
      this.sigma=Math.sqrt(this.p.D/this.p.gamma*(-Math.expm1(-2*this.p.gamma*this.p.dt)));
    }
    step() {
      const p=this.p,h=p.dt;
      // BAOAB splitting: kick, drift, exact Ornstein–Uhlenbeck, drift, kick.
      this.v+=h/2*force(this.x,this.t,p); this.x+=h/2*this.v;
      this.v=this.decay*this.v+this.sigma*this.random.normal();
      this.x+=h/2*this.v; this.t=(++this.steps)*h;
      this.v+=h/2*force(this.x,this.t,p);
      if (!Number.isFinite(this.x)||!Number.isFinite(this.v)) throw new Error('Non-finite trajectory');
      // Hysteresis avoids counting recrossings of x=0 as separate transitions.
      const well=this.x>0.7?1:this.x< -0.7?-1:this.well;
      if(well!==this.well) {this.transitions++; if(this.lastTransition!==null)this.residences.push(this.t-this.lastTransition);this.lastTransition=this.t;this.well=well;}
      return this;
    }
  }
  function response(p, periods=16, burn=4) {
    const model=new Model(p), period=2*Math.PI/model.p.omega;
    const burnSteps=Math.round(burn*period/model.p.dt), n=Math.round(periods*period/model.p.dt);
    for(let i=0;i<burnSteps;i++)model.step();
    let sin=0,cos=0;
    for(let i=0;i<n;i++){model.step();sin+=model.x*Math.sin(model.p.omega*model.t);cos+=model.x*Math.cos(model.p.omega*model.t);}
    return {sin:2*sin/n,cos:2*cos/n};
  }
  function aggregate(samples) {
    const n=samples.length, s=samples.reduce((a,b)=>a+b.sin,0)/n,c=samples.reduce((a,b)=>a+b.cos,0)/n;
    const amplitude=Math.hypot(s,c);
    // Delta-method standard error of the amplitude of the ensemble mean phasor.
    const variance=n>1?samples.reduce((a,b)=>a+((b.sin-s)*(amplitude?s/amplitude:1)+(b.cos-c)*(amplitude?c/amplitude:0))**2,0)/(n-1):0;
    return {amplitude,se:Math.sqrt(variance/n),n};
  }
  const api={defaults,limits,validate,Random,potential,force,Model,response,aggregate};
  if(typeof module!=='undefined'&&module.exports)module.exports=api; else root.Physics=api;
})(typeof globalThis!=='undefined'?globalThis:this);
