import {el} from './dom.js';
import {styleDisclosure} from './style-phases.js';

export const dimensionNames={palette:'配色',typography:'文字层级',density:'密度',composition:'构图',spacing:'间距',lines:'线条',icons:'图标'};
const intentNames={initial_design:'初始设计',restyle:'调整已有设计',feasibility:'版式可行性'};
export function recipeOrigin(recipe,label){
  if(recipe.schema_version==='style_recipe.v3')return intentNames[recipe.intent]||recipe.intent;
  if(recipe.schema_version==='style_recipe.v2')return '外部图片 · '+recipe.reference_sources.references.length+' 份固定参考';
  return '项目页面 · '+label(recipe.input.reference.page_id);
}
export function recipeRules(recipe){
  return recipe.schema_version==='style_recipe.v3'?recipe.parameters:recipe.dimensions;
}
function readable(value){
  if(Array.isArray(value))return value.length?value.map(readable).join('；'):'未记录';
  if(value&&typeof value==='object')return Object.entries(value).map(([key,child])=>`${key}：${readable(child)}`).join('；');
  return String(value??'未记录');
}
export function recipeDetails(recipe,label){
  const rules=recipeRules(recipe);
  const ruleList=el('dl',{class:'recipe-rules'},Object.entries(dimensionNames).filter(([key])=>key in rules).flatMap(([key,title])=>[el('dt',{},title),el('dd',{},readable(rules[key]))]));
  if(recipe.schema_version!=='style_recipe.v3')return ruleList;
  return el('div',{class:'stack'},ruleList,
    el('h3',{},'版式依据'),el('p',{},recipe.input.layout_rationale),
    el('h3',{},'代表页与覆盖范围'),el('ul',{},recipe.input.sample_targets.map(item=>el('li',{},label(item.page_id)+' · '+item.coverage_risks.join('、')))),
    el('p',{class:'muted'},'尚未覆盖：'+readable(recipe.input.uncovered_cases)),
    el('p',{class:'muted'},'设计取舍：'+readable(recipe.input.tradeoffs)),
    styleDisclosure('逐页职责与允许的差异',el('ul',{},recipe.input.page_profiles.map(item=>el('li',{},label(item.page_id)+' · '+item.profile+' · '+item.task+' · '+item.density))),el('p',{},'允许调整：'+readable(rules.allowed_overrides)),el('p',{},'逐页规则：'+readable(rules.page_rules))));
}
