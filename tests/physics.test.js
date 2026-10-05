'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const P=require('../js/physics');
test('potential minima, barrier and derivative agree with the model',()=>{
  assert.ok(Math.abs(P.potential(Math.SQRT2)+.5)<1e-14);
  assert.equal(P.potential(0),0);
  for(const x of [-2,-.5,0,.8,2]){const h=1e-6;assert.ok(Math.abs(P.force(x,0,{...P.defaults,f:0})+(P.potential(x+h)-P.potential(x-h))/(2*h))<1e-8);}
});
test('invalid parameters fail before integration',()=>{
  for(const p of [{T:-1},{T:NaN},{gamma:0},{omega:0},{dt:1},{seed:.5},{seed:Infinity}])assert.throws(()=>new P.Model(p),RangeError);
});
test('seed reproduces a trajectory; different seeds change it',()=>{
  const a=new P.Model(),b=new P.Model(),c=new P.Model({seed:43});
  for(let i=0;i<10000;i++){a.step();b.step();c.step();}
  assert.equal(a.x,b.x);assert.equal(a.v,b.v);assert.notEqual(a.x,c.x);
});
test('Gaussian generator has zero mean and unit variance',()=>{
  const r=new P.Random(19);let s=0,q=0;for(let i=0;i<100000;i++){const x=r.normal();s+=x;q+=x*x;}
  assert.ok(Math.abs(s/100000)<.015);assert.ok(Math.abs(q/100000-1)<.025);
});
test('noiseless undriven particle remains at the minimum',()=>{
  const m=new P.Model({T:0,f:0});for(let i=0;i<20000;i++)m.step();assert.ok(Math.abs(m.x+Math.SQRT2)<1e-12);assert.equal(m.transitions,0);
});
test('equilibrium kinetic temperature is T (independent of gamma) and converges with step refinement',()=>{
  const values=[];
  for(const dt of [.02,.01]){const m=new P.Model({T:.4,f:0,dt});let s=0,n=0;for(let i=0;i<20000/dt;i++){m.step();if(m.t>500){s+=m.v*m.v;n++;}}const value=s/n;values.push(value);assert.ok(Math.abs(value-.4)<.025);}
  assert.ok(Math.abs(values[0]-values[1])<.02);
  const m=new P.Model({T:.4,gamma:2,f:0});let s=0,n=0;for(let i=0;i<500000;i++){m.step();if(m.t>500){s+=m.v*m.v;n++;}}assert.ok(Math.abs(s/n-.4)<.02);
});
test('extreme UI parameters remain finite',()=>{
  for(const T of [0,1.5])for(const gamma of [.3,3]){const m=new P.Model({T,gamma,f:.5,omega:.2});for(let i=0;i<100000;i++)m.step();assert.ok(Number.isFinite(m.x)&&Number.isFinite(m.v));}
});

test('adjustable wells have correct minima, barrier, and force',()=>{
  for(const a of [.1,1,2])for(const b of [.01,.5,2]){
    const p={...P.defaults,a,b,f:0}; const x=Math.sqrt(a/b);
    assert.ok(Math.abs(P.potential(x,p)+a*a/(4*b))<1e-10);
    assert.ok(Math.abs(P.force(x,0,p))<1e-10);
    assert.equal(P.barrier(p),a*a/(4*b));
    const m=new P.Model({...p,T:0});for(let i=0;i<1000;i++)m.step();assert.ok(Math.abs(m.x+x)<1e-10);
  }
});
test('temperature and damping satisfy fluctuation-dissipation',()=>{
  for(const gamma of [.3,1,3]){
    const p={...P.defaults,gamma,T:.4};const m=new P.Model(p);
    assert.equal(P.noiseIntensity(p),gamma*.4);
    assert.ok(Math.abs(m.sigma*m.sigma-.4*(1-Math.exp(-2*gamma*p.dt)))<1e-14);
  }
});
test('disabled force equals f=0 and retains chosen amplitude',()=>{
 const off=new P.Model({driveEnabled:false,f:.4}),zero=new P.Model({f:0});
 for(let i=0;i<10000;i++){off.step();zero.step();}
 assert.equal(off.x,zero.x);assert.equal(off.v,zero.v);assert.equal(off.p.f,.4);
 assert.equal(P.drive(5,off.p),0);
});
test('flat and single-well cases work; unbounded potential is rejected',()=>{
 assert.throws(()=>new P.Model({a:1,b:0}),RangeError);
 for(const b of [0,.5]){const m=new P.Model({a:0,b,T:0,driveEnabled:false});for(let i=0;i<10000;i++)m.step();assert.equal(m.x,0);assert.equal(m.transitions,0);}
});
test('extreme potential coefficients remain stable at highest temperature',()=>{
 for(const a of [0,2])for(const b of [.01,2])for(const gamma of [.3,3]){
 const m=new P.Model({a,b,gamma,T:1.5,f:.5});for(let i=0;i<30000;i++)m.step();assert.ok(Number.isFinite(m.x));
 }
});
