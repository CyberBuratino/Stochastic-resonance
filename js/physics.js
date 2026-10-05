/* Dimensionless inertial Langevin model. Usable offline and in Node tests. */
(function (root) {
  'use strict';
  const defaults = Object.freeze({ T: 0.22, a: 1, b: 0.5, driveEnabled: true, f: 0.18, omega: 0.04, gamma: 1, dt: 0.02, seed: 42 });
  const limits = {T:[0,1.5], a:[0,2], b:[0,2], f:[0,0.5], omega:[0.02,0.2], gamma:[0.3,3], dt:[0.005,0.04], seed:[0,4294967295]};
  function validate(p) {
    for (const [k,[lo,hi]] of Object.entries(limits)) if (!Number.isFinite(p[k]) || p[k]<lo || p[k]>hi) throw new RangeError(k);
    if (typeof p.driveEnabled !== 'boolean') throw new RangeError('driveEnabled');
    if (p.b === 0 && p.a > 0) throw new RangeError('b: unconfined potential');
    if (!Number.isInteger(p.seed)) throw new RangeError('seed');
    return p;
  }
  class Random {
    constructor(seed) { this.state=seed>>>0; }
    uniform() { let t=this.state=(this.state+0x6D2B79F5)>>>0; t=Math.imul(t^(t>>>15),t|1); t^=t+Math.imul(t^(t>>>7),t|61); return ((t^(t>>>14))>>>0)/4294967296; }
    normal() { return Math.sqrt(-2*Math.log(1-this.uniform()))*Math.cos(2*Math.PI*this.uniform()); }
  }
  const potential = (x,p=defaults) => -p.a*x*x/2+p.b*x**4/4;
  const drive = (t,p) => p.driveEnabled ? p.f*Math.sin(p.omega*t) : 0;
  const force = (x,t,p) => p.a*x-p.b*x**3+drive(t,p);
  const noiseIntensity = p => p.gamma*p.T;
  const wellPosition = p => p.a>0 && p.b>0 ? Math.sqrt(p.a/p.b) : 0;
  const barrier = p => p.b>0 ? p.a*p.a/(4*p.b) : 0;
  const criticalForce = p => p.a>0 && p.b>0 ? 2*p.a/3*Math.sqrt(p.a/(3*p.b)) : 0;
  class Model {
    constructor(p={}) {
      this.p=validate({...defaults,...p}); this.random=new Random(this.p.seed);
      this.t=0; this.x=this.p.a>0 ? -wellPosition(this.p) : 0; this.v=0; this.steps=0; this.transitions=0; this.well=-1; this.lastTransition=null; this.residences=[];
      this.decay=Math.exp(-this.p.gamma*this.p.dt);
      this.sigma=Math.sqrt(this.p.T*(-Math.expm1(-2*this.p.gamma*this.p.dt)));
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
      const threshold=wellPosition(p)/2;
      const well=threshold>0 ? (this.x>threshold?1:this.x< -threshold?-1:this.well) : this.well;
      if(well!==this.well) {this.transitions++; if(this.lastTransition!==null)this.residences.push(this.t-this.lastTransition);this.lastTransition=this.t;this.well=well;}
      return this;
    }
  }
  const api={defaults,limits,validate,Random,potential,drive,force,noiseIntensity,wellPosition,barrier,criticalForce,Model};
  if(typeof module!=='undefined'&&module.exports)module.exports=api; else root.Physics=api;
})(typeof globalThis!=='undefined'?globalThis:this);
