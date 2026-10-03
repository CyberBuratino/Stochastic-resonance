'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const P=require('../js/physics');
test('potential minima, barrier and derivative agree with the model',()=>{
  assert.ok(Math.abs(P.potential(Math.SQRT2)+.5)<1e-14);
  assert.equal(P.potential(0),0);
  for(const x of [-2,-.5,0,.8,2]){const h=1e-6;assert.ok(Math.abs(P.force(x,0,{f:0,omega:1})+(P.potential(x+h)-P.potential(x-h))/(2*h))<1e-8);}
});
test('invalid parameters fail before integration',()=>{
  for(const p of [{D:-1},{D:NaN},{gamma:0},{omega:0},{dt:1},{seed:.5},{seed:Infinity}])assert.throws(()=>new P.Model(p),RangeError);
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
  const m=new P.Model({D:0,f:0});for(let i=0;i<20000;i++)m.step();assert.ok(Math.abs(m.x+Math.SQRT2)<1e-12);assert.equal(m.transitions,0);
});
test('equilibrium kinetic temperature is D/gamma and converges with step refinement',()=>{
  const values=[];
  for(const dt of [.02,.01]){const m=new P.Model({D:.4,f:0,dt});let s=0,n=0;for(let i=0;i<20000/dt;i++){m.step();if(m.t>500){s+=m.v*m.v;n++;}}const value=s/n;values.push(value);assert.ok(Math.abs(value-.4)<.025);}
  assert.ok(Math.abs(values[0]-values[1])<.02);
  const m=new P.Model({D:.4,gamma:2,f:0});let s=0,n=0;for(let i=0;i<500000;i++){m.step();if(m.t>500){s+=m.v*m.v;n++;}}assert.ok(Math.abs(s/n-.2)<.02);
});
test('default parameters demonstrate an interior response maximum',()=>{
  const amplitudes=[0,.22,1.5].map(D=>P.aggregate(Array.from({length:6},(_,j)=>P.response({...P.defaults,D,seed:42+j*7919}))).amplitude);
  assert.ok(amplitudes[1]>3*amplitudes[0]);assert.ok(amplitudes[1]>2*amplitudes[2]);
});
test('extreme UI parameters remain finite',()=>{
  for(const D of [0,1.5])for(const gamma of [.3,3]){const m=new P.Model({D,gamma,f:.5,omega:.2});for(let i=0;i<100000;i++)m.step();assert.ok(Number.isFinite(m.x)&&Number.isFinite(m.v));}
});
