import gdspy

def main():
	gdsii = gdspy.GdsLibrary(infile='build/sky130/user_project_wrapper_fixedup.gds')
	core = gdsii.cells['user_project_core_lambdasoc_cts']

	ties = 0
	decaps = 0
	ratio = 0.2

	for ref in core.references:
		if ref.ref_cell.name != "tie_diff_w2":
			continue
		ties += 1
		if decaps > (0.1 * ties):
			continue
		decaps += 1
		ref.ref_cell = gdsii.cells['decap_w0']
	gdsii.write_gds('build/sky130/user_project_wrapper_decap.gds')

if __name__ == '__main__':
	main()
