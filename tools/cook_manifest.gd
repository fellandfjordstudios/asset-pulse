## THE CATALOG'S COOK MANIFEST (the library's bake plan, step F): every target
## the explorer's bake planned -- the registry union the library's package
## targets, with their seeds, parameters, tags and styles -- written as one
## game manifest (`ops/game-manifest.schema.json`) for the library's
## `tools/cook.sh`. The set is the explorer's `plan()`, read and not copied, so
## it keeps one spelling. One profile, `catalog`: no triangle cap, so the cook
## ships every rung the bake makes (the catalog's zip carries every rung).
## Every subject casts `moving`: the catalog ships glTF, which carries no
## caster flag (`AgCook.lower_scene`), and `static` on a subject that moves
## itself is refused after its bake -- one such refusal fails the whole cook.
##
##   godot --headless --path library --script tools/cook_manifest.gd -- <out.json> <explorer dir>
extends SceneTree

const TARGET := "catalog"

func _init():
	var args := OS.get_cmdline_user_args()
	if args.size() != 2:
		printerr("usage: -- <out.json> <pinned explorer directory>")
		quit(2)
		return
	var reg := AgLibrary.registry()
	var planner = load(args[1] + "/tools/bake-library.gd")
	var subjects := []
	for spec in planner.plan(reg, planner.upstream_targets()):
		var id := String(spec["id"])
		var tag := String(spec.get("tag", ""))
		var v := {"seed": int(spec.get("seed", planner.DEFAULT_SEED)), "params": spec.get("params", {})}
		if tag != "":
			v["tag"] = tag
		if String(spec.get("style", "")) != "":
			v["style"] = String(spec["style"])
		subjects.append({"subject": id.replace("/", "-") + ("-" + tag if tag != "" else ""), "generator": id, "variants": [v]})
	var m := {
		"schema": "game-manifest-1",
		"name": "asset-pulse-catalog",
		"targets": [TARGET],
		"profiles": {TARGET: {"bias_octaves": 0.0, "rung_triangles_max": 2147483647}},
		"settings": {"default": {"casters": "moving"}},
		"subjects": subjects,
	}
	var f := FileAccess.open(args[0], FileAccess.WRITE)
	if f == null:
		printerr("cannot write %s" % args[0])
		quit(3)
		return
	f.store_string(JSON.stringify(m, "  "))
	f.close()
	print("cook manifest: %d subject(s), target %s, at %s" % [subjects.size(), TARGET, args[0]])
	quit()
