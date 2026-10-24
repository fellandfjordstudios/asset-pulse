## THE BAKE KEYS OF THE SUBJECTS NAMED, for tools/bake.sh's ledger of tries.
##
##   godot --headless --path library --script <abs path to this> -- <explorer bake-library.gd> <material rung> <stem>...
##
## One JSON object, stem -> one key for the whole subject: the library's own
## rung keys (AgBakeKey.cache_for, `plans/062`) joined, so it moves exactly
## when something a rung is made from moved. The targets are the explorer's
## (its static `plan`, the registry with the library's own targets), read and
## not copied; only the Target is made here, as the explorer makes it. A stem
## whose rungs cannot be keyed is "".
extends SceneTree

func _init() -> void:
	var argv := Array(OS.get_cmdline_user_args())
	if argv.size() < 2:
		printerr("usage: -- <explorer bake-library.gd> <material rung> <stem>...")
		quit(2)
		return
	var explorer = load(String(argv[0]))
	var material_rung := int(argv[1])
	var stems := argv.slice(2)
	var reg := AgLibrary.registry()
	var targets: Array = []
	for t in explorer.plan(reg, AgPublish.package_targets()):
		var style_name := String(t.get("style", ""))
		var target := AgBaker.Target.new(String(t["id"]), t.get("params", {}), int(t.get("seed", 1)),
			String(t.get("tag", "")), [], AgStyle.named(style_name) if style_name != "" else null)
		if stems.has(target.stem()):
			targets.append(target)
	var keys: Dictionary = AgBakeKey.cache_for(reg, targets, material_rung, true)["keys"]
	var out := {}
	for s in stems:
		var prefix := String(s) + "-r"
		var rungs: Array = keys.keys().filter(func(k): return String(k).begins_with(prefix) \
			and String(k).trim_prefix(prefix).is_valid_int())
		rungs.sort()
		out[String(s)] = "" if rungs.is_empty() else AgContentHash.of_string(
			"\n".join(PackedStringArray(rungs.map(func(k): return "%s %s" % [k, keys[k]]))))
	print(JSON.stringify(out))
	quit(0)
