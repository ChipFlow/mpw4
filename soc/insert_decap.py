import gdspy

def main():
	gdsii = gdspy.GdsLibrary(infile='build/sky130/user_project_wrapper_fixedup.gds')
	core = gdsii.cells['user_project_core_lambdasoc_cts']
	decaps = []

	tie_by_xyr = {}
	def get_key(ref):
		return (ref.origin[0], ref.origin[1], ref.rotation, ref.x_reflection)

	for ref in core.references:
		if ref.ref_cell.name != "tie_diff":
			continue
		tie_by_xyr[get_key(ref)] = ref

	xstep = 1.0
	width = 2

	# Replace 20% of suitable ties with decap
	ratio = 0.2
	decaps = []
	candidates = 0
	replaced = set()

	for key in sorted(tie_by_xyr.keys()):
		x0, y0, r0, f0 = key
		is_cand = True
		ties = []
		keys = []
		for i in range(width):
			ki = (x0 + i * xstep, y0, r0, f0)
			if ki not in tie_by_xyr:
				is_cand = False
				break
			if ki in replaced: # already replaced by a decap
				is_cand = False
				break
			keys.append(ki)
			ties.append(tie_by_xyr[ki])
		if not is_cand:
			continue
		candidates += 1
		if len(decaps) > (candidates * ratio):
			continue
		decaps.append(gdspy.CellReference("decap_w0", origin=(x0, y0), rotation=r0,
			magnification=ties[0].magnification, x_reflection=f0))
		for k in keys:
			replaced.add(k)

	print(f"Inserted {len(decaps)}/{candidates} decaps ({100*len(decaps)/candidates:.0f}%)")

	new_refs = [r for r in core.references if get_key(r) not in replaced]
	new_refs += decaps

	core.references = new_refs

	gdsii.write_gds('build/sky130/user_project_wrapper_decap.gds')

if __name__ == '__main__':
	main()