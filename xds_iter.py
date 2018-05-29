import sys
import argparse
import subprocess
import re
import os

def set_xds_inp_crystal_form(args):
  subprocess.call(["mv", "XDS.INP", "XDS.INP.old"])
  f_in  = open("XDS.INP.old", "r")
  f_out = open("XDS.INP", "a")
  for line in f_in.readlines():
    if "SPACE_GROUP_NUMBER" in line:
      # For PTP1B: 152
      f_out.write("SPACE_GROUP_NUMBER= %s \n" % args.space_group_num)
    elif "UNIT_CELL_CONSTANTS" in line:
      # For PTP1B:
      # 88,88,104,90,90,120
      # 88 88 104 90 90 120
      ucs_str = " ".join(args.unit_cell_constants.split(","))
      f_out.write("UNIT_CELL_CONSTANTS= %s\n" % ucs_str)
    else:
      f_out.write(line,)
  f_in.close()
  f_out.close()

def set_xds_inp_resol_range(curr_resol):
  subprocess.call(["mv", "XDS.INP", "XDS.INP.old"])
  f_in  = open("XDS.INP.old", "r")
  f_out = open("XDS.INP", "a")
  for line in f_in.readlines():
    if line.strip().startswith("INCLUDE_RESOLUTION_RANGE"):
      f_out.write("INCLUDE_RESOLUTION_RANGE= 80 %.2f \n" % curr_resol)
    else:
      f_out.write(line,)
  f_in.close()
  f_out.close()

def set_xds_inp_jobs(jobs):
  subprocess.call(["mv", "XDS.INP", "XDS.INP.old"])
  f_in  = open("XDS.INP.old", "r")
  f_out = open("XDS.INP", "a")
  for line in f_in.readlines():
    if "JOB" in line:
      f_out.write("JOB= %s\n" % jobs)
    else:
      f_out.write(line,)
  f_in.close()
  f_out.close()

def conditions_met(args):
  # Parse CORRECT.LP, find table with final stats by resolution bin, 
  # and decide if our conditions are all met for the highest-resolution bin.
  # We are trusting that CORRECT divvies up reflections into appropriately sized
  # bins, such that we can simply read from the last (high-resolution) bin.
  # We also take advantage of the fact that versions of this table appear throughout
  # CORRECT.LP, but earlier ones are for subsets of the data and the final one is 
  # for the entire dataset, which is what we care about.
  compl = None
  i_sigma = None
  cc_half = None
  cc_half_signif = False
  f = open("CORRECT.LP", "r")
  pattern = r'^(\s+)(\d+)\.(\d{2})(\s+)(\d+)(\s+)(\d+)'
  for line in f.readlines():
    if re.match(pattern, line):
      parts = line.split()
      compl   = float(parts[4].split("%")[0])
      i_sigma = float(parts[8])
      cc_half = float(parts[10].split("*")[0])
      if "*" in parts[10]:
        cc_half_signif = True
      else:
        cc_half_signif = False # because this can be set to True by earlier lines (lower-resol bins),
                               # but we want its final value to reflect the last line (highest-resol bin)
  assert compl is not None and i_sigma is not None and cc_half is not None, \
    "Error: Couldn't find completeness, I/sigma, and/or CC1/2.  Did XDS fail?!"
  if compl >= args.min_compl and i_sigma >= args.min_i_sigma and cc_half >= args.min_cc_half and cc_half_signif:
    print compl, ">=", args.min_compl
    print i_sigma, ">=", args.min_i_sigma
    print cc_half, ">=", args.min_cc_half
    return True
  return False

if __name__ == "__main__":
  
  # Parse command-line arguments
  parser = argparse.ArgumentParser()
  parser.add_argument('--images', action="store", dest="image_fn_template", type=str, required=True)
  parser.add_argument('--min_complete', action="store", dest="min_compl", type=float, default=90.)
  parser.add_argument('--min_i_sigma', action="store", dest="min_i_sigma", type=float, default=1.0)
  parser.add_argument('--min_cc_half', action="store", dest="min_cc_half", type=float, default=50.)
  parser.add_argument('--start_resol', action="store", dest="high_resol", type=float, default=1.4)
  parser.add_argument('--resol_step_size', action="store", dest="resol_step_size", type=float, default=0.05)
  parser.add_argument('--max_resol', action="store", dest="max_resol", type=float, default=3.5)
  parser.add_argument('--space_group_num', action="store", dest="space_group_num", type=str)
  parser.add_argument('--unit_cell_constants', action="store", dest="unit_cell_constants", type=str)
  parser.add_argument('--only_correct_loops', dest='only_correct_loops', action='store_true', default=False)
  args = parser.parse_args()
  assert args.min_cc_half > 1., "Error: Min CC1/2 provided should be on the 0-100 scale!"

  # Initial XDS run with liberally high resolution (expectation is this will not meet our criteria)
  subprocess.call(["generate_XDS.INP", "\"%s\"" % args.image_fn_template]) # include quotes
  if args.space_group_num and args.unit_cell_constants:
    set_xds_inp_crystal_form(args)
  else: 
    print >> sys.stderr, "Space group number and unit cell constants not specified; using XDS defaults"
  curr_resol = args.high_resol
  set_xds_inp_resol_range(curr_resol)
  if not args.only_correct_loops:
    # Run through IDXREF first.  IDXREF will throw an error about un-indexed reflections in ~20% of cases.
    # In a lot of cases this is fine -- we think it may just be because we are *initially* processing at 
    # ultra-high resolution.  We will rely on subsequent xds steps to flag these datasets as crappy.
    # Worst case, our CORRECT loop (below) will never find a resolution at which our criteria are met
    # before it reaches the max resolution we want to consider, so the process will die there.
    set_xds_inp_jobs("XYCORR INIT COLSPOT IDXREF")
    subprocess.call(["xds"])
    # Run the remaining steps following IDXREF
    set_xds_inp_jobs("DEFPIX INTEGRATE CORRECT")
    subprocess.call(["xds"])
    subprocess.call(["cp", "CORRECT.LP", "CORRECT.LP_%.2f" % curr_resol])

  # Iterate CORRECT as needed, slowly backing off on high resolution
  set_xds_inp_jobs("CORRECT")
  if not os.path.exists("CORRECT.LP"):
    # This is probably only true if --only_correct_loops is used and CORRECT.LP has been deleted
    subprocess.call(["xds"])
    subprocess.call(["cp", "CORRECT.LP", "CORRECT.LP_%.2f" % curr_resol])
  while not conditions_met(args) and curr_resol <= args.max_resol:
    curr_resol += args.resol_step_size
    set_xds_inp_resol_range(curr_resol)
    subprocess.call(["xds"])
    subprocess.call(["cp", "CORRECT.LP", "CORRECT.LP_%.2f" % curr_resol])
  good_resol = curr_resol

  # Iterate CORRECT in the opposite direction back toward higher resolution,
  # but in smaller increments, to settle on the very highest resolution limit
  # that meets all our criteria.  Should go less than resol_step_size, at most.
  import math
  n_iters = int(math.ceil(args.resol_step_size / 0.01))  # 5 iterations by default
  for n in range(1, n_iters):
    curr_resol = good_resol - (0.01 * n)
    set_xds_inp_resol_range(curr_resol)
    subprocess.call(["xds"])
    subprocess.call(["cp", "CORRECT.LP", "CORRECT.LP_%.2f" % curr_resol])
    if not conditions_met(args):
      # We went just too far -- undo this last step
      print "%.2f A is too far -- backing off by 0.01 A" % curr_resol
      curr_resol += 0.01
      break
  best_resol = curr_resol
  
  # Re-run with the final best resolution, since we (likely?) over-shot a second ago,
  # to get the final XDS_ASCII.HKL
  set_xds_inp_resol_range(best_resol)
  subprocess.call(["xds"])
  subprocess.call(["cp", "CORRECT.LP", "CORRECT.LP_%.2f_FINAL" % curr_resol])

  # Convert from HKL to MTZ with xdsconv 
  f = open("XDSCONV.INP", "w")
  f.write("""
INPUT_FILE= XDS_ASCII.HKL
OUTPUT_FILE= temp.hkl CCP4
FRIEDEL'S_LAW= TRUE""")
  f.close()
  subprocess.call(["xdsconv"])
  g = open("run_xdsconv.sh", "w")
  g.write("""
f2mtz HKLOUT temp.mtz<F2MTZ.INP
cad HKLIN1 temp.mtz HKLOUT XDS_ASCII.mtz<<EOF
LABIN FILE 1 ALL
END
EOF""")
  g.close()
  subprocess.call(["source", "run_xdsconv.sh"])
  
  print "********** Done at %.2f A! **********" % best_resol
