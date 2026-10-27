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
## LEFT OUT, BY NAME, EVERY RUN: a styled target whose style binds a generator
## (`AgStyle.form`) that `AgLibrary.registry_for` does not load for it. The
## cook's workers and its final pass load only what an item's generator and
## its children reach (plans/107 step 6), so such an item fails in its worker
## and `tools/cook.sh` stops the whole cook (`stone-rock-clump-toon`, whose
## `style/dungeon-toon` binds `stone/pebble-toon`; filed in the library's
## feedback/). The catalog serves its last good build meanwhile. The test is
## the library's own two functions, so this stops leaving it out once
## `registry_for` follows a style's bindings.
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
	var left_out := 0
	for spec in planner.plan(reg, planner.upstream_targets()):
		var id := String(spec["id"])
		var tag := String(spec.get("tag", ""))
		var style := AgStyle.named(String(spec.get("style", ""))) if String(spec.get("style", "")) != "" else null
		if style != null:
			var reach := AgLibrary.registry_for([id])
			var unreached := style.form.values().filter(func(b): return not reach.has(String(b)))
			if not unreached.is_empty():
				left_out += 1
				print("cook manifest: LEFT OUT %s: its style %s binds %s, which the cook's per-item registry (AgLibrary.registry_for) does not load, so its worker would fail the whole cook (filed in the library's feedback/); the catalog serves its last good build"
					% [id.replace("/", "-") + ("-" + tag if tag != "" else ""), style.name, ", ".join(PackedStringArray(unreached))])
				continue
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
	print("cook manifest: %d subject(s), %d left out, target %s, at %s" % [subjects.size(), left_out, TARGET, args[0]])
	quit()
