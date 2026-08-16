import{p as U}from"./chunk-4BMEZGHF-CM9hKG6X.js";import{aD as y,av as z,b6 as Z,a5 as j,R as q,T as H,z as J,B as K,D as Q,C as X,_ as p,O as F,Z as Y,E as tt,a6 as et,aa as at,ag as rt,P as nt}from"./index-BEKg0fyB.js";import{p as it}from"./radar-MK3ICKWK-BiwX3bFF.js";import{d as W}from"./arc-De33OH-a.js";import{o as st}from"./ordinal-Cboi1Yqb.js";import"./semi-ui-_6AzNf7V.js";import"./react-core-D-iPSUlg.js";import"./i18n-grwXA2Qn.js";import"./tools-DKoQC5FQ.js";import"./react-components-BnylIsR_.js";import"./_baseUniq-D0VflObF.js";import"./_basePickBy-DGymMZ9n.js";import"./clone-ZKT81_Ff.js";import"./init-Gi6I4Gst.js";function ot(t,a){return a<t?-1:a>t?1:a>=t?0:NaN}function lt(t){return t}function ct(){var t=lt,a=ot,m=null,o=y(0),u=y(z),x=y(0);function i(e){var r,l=(e=Z(e)).length,g,A,h=0,c=new Array(l),n=new Array(l),v=+o.apply(this,arguments),D=Math.min(z,Math.max(-z,u.apply(this,arguments)-v)),f,T=Math.min(Math.abs(D)/l,x.apply(this,arguments)),$=T*(D<0?-1:1),d;for(r=0;r<l;++r)(d=n[c[r]=r]=+t(e[r],r,e))>0&&(h+=d);for(a!=null?c.sort(function(S,w){return a(n[S],n[w])}):m!=null&&c.sort(function(S,w){return m(e[S],e[w])}),r=0,A=h?(D-l*$)/h:0;r<l;++r,v=f)g=c[r],d=n[g],f=v+(d>0?d*A:0)+$,n[g]={data:e[g],index:r,value:d,startAngle:v,endAngle:f,padAngle:T};return n}return i.value=function(e){return arguments.length?(t=typeof e=="function"?e:y(+e),i):t},i.sortValues=function(e){return arguments.length?(a=e,m=null,i):a},i.sort=function(e){return arguments.length?(m=e,a=null,i):m},i.startAngle=function(e){return arguments.length?(o=typeof e=="function"?e:y(+e),i):o},i.endAngle=function(e){return arguments.length?(u=typeof e=="function"?e:y(+e),i):u},i.padAngle=function(e){return arguments.length?(x=typeof e=="function"?e:y(+e),i):x},i}var N=j.pie,G={sections:new Map,showData:!1,config:N},b=G.sections,O=G.showData,pt=structuredClone(N),ut=p(()=>structuredClone(pt),"getConfig"),gt=p(()=>{b=new Map,O=G.showData,Y()},"clear"),dt=p(({label:t,value:a})=>{b.has(t)||(b.set(t,a),F.debug(`added new section: ${t}, with value: ${a}`))},"addSection"),ft=p(()=>b,"getSections"),mt=p(t=>{O=t},"setShowData"),ht=p(()=>O,"getShowData"),I={getConfig:ut,clear:gt,setDiagramTitle:q,getDiagramTitle:H,setAccTitle:J,getAccTitle:K,setAccDescription:Q,getAccDescription:X,addSection:dt,getSections:ft,setShowData:mt,getShowData:ht},vt=p((t,a)=>{U(t,a),a.setShowData(t.showData),t.sections.map(a.addSection)},"populateDb"),St={parse:p(async t=>{const a=await it("pie",t);F.debug(a),vt(a,I)},"parse")},yt=p(t=>`
  .pieCircle{
    stroke: ${t.pieStrokeColor};
    stroke-width : ${t.pieStrokeWidth};
    opacity : ${t.pieOpacity};
  }
  .pieOuterCircle{
    stroke: ${t.pieOuterStrokeColor};
    stroke-width: ${t.pieOuterStrokeWidth};
    fill: none;
  }
  .pieTitleText {
    text-anchor: middle;
    font-size: ${t.pieTitleTextSize};
    fill: ${t.pieTitleTextColor};
    font-family: ${t.fontFamily};
  }
  .slice {
    font-family: ${t.fontFamily};
    fill: ${t.pieSectionTextColor};
    font-size:${t.pieSectionTextSize};
    // fill: white;
  }
  .legend text {
    fill: ${t.pieLegendTextColor};
    font-family: ${t.fontFamily};
    font-size: ${t.pieLegendTextSize};
  }
`,"getStyles"),xt=yt,At=p(t=>{const a=[...t.entries()].map(o=>({label:o[0],value:o[1]})).sort((o,u)=>u.value-o.value);return ct().value(o=>o.value)(a)},"createPieArcs"),Dt=p((t,a,m,o)=>{F.debug(`rendering pie chart
`+t);const u=o.db,x=tt(),i=et(u.getConfig(),x.pie),e=40,r=18,l=4,g=450,A=g,h=at(a),c=h.append("g");c.attr("transform","translate("+A/2+","+g/2+")");const{themeVariables:n}=x;let[v]=rt(n.pieOuterStrokeWidth);v??(v=2);const D=i.textPosition,f=Math.min(A,g)/2-e,T=W().innerRadius(0).outerRadius(f),$=W().innerRadius(f*D).outerRadius(f*D);c.append("circle").attr("cx",0).attr("cy",0).attr("r",f+v/2).attr("class","pieOuterCircle");const d=u.getSections(),S=At(d),w=[n.pie1,n.pie2,n.pie3,n.pie4,n.pie5,n.pie6,n.pie7,n.pie8,n.pie9,n.pie10,n.pie11,n.pie12],C=st(w);c.selectAll("mySlices").data(S).enter().append("path").attr("d",T).attr("fill",s=>C(s.data.label)).attr("class","pieCircle");let P=0;d.forEach(s=>{P+=s}),c.selectAll("mySlices").data(S).enter().append("text").text(s=>(s.data.value/P*100).toFixed(0)+"%").attr("transform",s=>"translate("+$.centroid(s)+")").style("text-anchor","middle").attr("class","slice"),c.append("text").text(u.getDiagramTitle()).attr("x",0).attr("y",-400/2).attr("class","pieTitleText");const M=c.selectAll(".legend").data(C.domain()).enter().append("g").attr("class","legend").attr("transform",(s,E)=>{const k=r+l,_=k*C.domain().length/2,B=12*r,V=E*k-_;return"translate("+B+","+V+")"});M.append("rect").attr("width",r).attr("height",r).style("fill",C).style("stroke",C),M.data(S).append("text").attr("x",r+l).attr("y",r-l).text(s=>{const{label:E,value:k}=s.data;return u.getShowData()?`${E} [${k}]`:E});const L=Math.max(...M.selectAll("text").nodes().map(s=>(s==null?void 0:s.getBoundingClientRect().width)??0)),R=A+e+r+l+L;h.attr("viewBox",`0 0 ${R} ${g}`),nt(h,g,R,i.useMaxWidth)},"draw"),wt={draw:Dt},Nt={parser:St,db:I,renderer:wt,styles:xt};export{Nt as diagram};
