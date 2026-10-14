## Export a missing terminal impostor through the pinned library APIs.
## Geometry, framing, style and serialization remain library-owned.
extends SceneTree
func _init():
 var args=OS.get_cmdline_user_args()
 if args.size()!=2:
  printerr('usage: -- <asset stem> <pinned explorer directory>')
  quit(2);return
 var wanted=args[0]
 var reg=AgLibrary.registry()
 var planner=load(args[1]+'/tools/bake-library.gd')
 for spec in planner.plan(reg,planner.upstream_targets()):
  var style=AgStyle.named(spec['style']) if spec.get('style','') != '' else null
  if spec.get('style','')!='' and style==null:
   printerr('Declared style is unavailable');quit(2);return
  var target=AgBaker.Target.new(spec['id'],spec.get('params',{}),int(spec.get('seed',1)),spec.get('tag',''),[],style)
  if target.stem()!=wanted:continue
  var g=reg.get_generator(target.id)
  var made=AgImpostorRung.of_entry(g,target.params,target.seed_value)
  if made.is_empty():quit(2);return
  var asset=made['asset']
  if style!=null:style.apply_to(asset)
  var out='res://build/impostor-repair'
  DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(out))
  var stem=target.stem()+'-r'+str(made['rung'])
  var glb=stem+'.glb'
  var scene=stem+'.scn'
  var err=AgBaker.write_gltf(asset,ProjectSettings.globalize_path(out+'/'+glb))
  if err!='':printerr(err);quit(3);return
  if ResourceSaver.save(AgBaker.scene_for(asset),out+'/'+scene)!=OK:quit(4);return
  err=AgBaker._verify(out+'/'+scene,asset)
  if err!='':printerr(err);quit(5);return
  var atlas=target.stem()+'-impostor.png'
  if not FileAccess.file_exists('res://build/artifacts/'+atlas):quit(6);return
  var row={'rung':int(made['rung']),'gltf':glb,'scene':scene,'triangles':asset.stats['triangles'],'vertices':asset.stats['vertices'],'impostor':asset.stats['impostor'],'atlas_file':atlas,'fingerprint':asset.fingerprint()}
  var f=FileAccess.open(out+'/'+target.stem()+'.json',FileAccess.WRITE)
  f.store_string(JSON.stringify(row,'  '));f.close()
  print('REPAIRED ',target.stem(),' rung ',made['rung'])
  quit();return
 quit(7)
