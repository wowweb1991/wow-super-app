const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const source = fs.readFileSync(path.join(__dirname,'../static/omni-extra-tools.js'),'utf8');
const tools = vm.runInNewContext(source.replace(/  const container = document.querySelector\('main'\);[\s\S]*$/, '  return tools;\n})();'));
const cases = [
['Percentage Calculator',[200,15],/^30$/],
['Percentage Change',[100,125],/^25%$/],
['Markup Calculator',[100,20],/120/],
['Gross Margin Calculator',[100,60],/40%/],
['Bill Splitter',[10,3],/3\.34/],
['Unit Price Calculator',[100,4],/25/],
['Break-even Calculator',[100,20,10],/^10 whole/],
['Budget Balance',[100,120],/Over budget/],
['Temperature Converter',[32,'Fahrenheit'],/^0 °C/],
['Speed Converter',[36,'km/h'],/10 m\/s/],
['Date Difference',['2024-02-28','2024-03-01'],/^2 days/],
['Add Days to Date',['2024-02-28',1],/February 29/],
['Time Duration',['23:30','01:00'],/^1 hours, 30 minutes$/],
['Text Case Converter',['Abc','UPPERCASE'],/^ABC$/],
['Line Sorter',['b\na','A to Z'],/^a\nb$/],
['Duplicate Line Remover',['a\nb\na'],/^a\nb$/],
['Whitespace Cleaner',[' a   b '],/^a b$/],
['Find and Replace',['a a','a','$&'],/^\$& \$&$/],
['JSON Formatter',['{"n":9007199254740993}','Compact'],/^\{"n":9007199254740993\}$/],
['URL Component Encoder',['a b','Encode'],/^a%20b$/]
];
for(const [name,args,expected] of cases) test(name,()=> {
 const tool=tools.find(t=>t[0]===name); assert.ok(tool); assert.match(tool[2](...args),expected);
});
test('all extra tools covered',()=>assert.equal(tools.length,cases.length));
test('invalid inputs rejected',()=>{
 for(const [name,args] of [['Break-even Calculator',[100,10,10]],['Temperature Converter',[-1,'Kelvin']],['JSON Formatter',['{','Compact']],['URL Component Encoder',['%','Decode']]]) assert.throws(()=>tools.find(t=>t[0]===name)[2](...args));
});
