xds\_iter.py
============

## Author:

Daniel Keedy

## Summary:

Starts from a series of diffraction images and processes with XDS, iterating
the final scaling step CORRECT step by adjusting high-resolution limit each time
until thresholds on completeness, I/sigmaI, and CC1/2 (default or user-provided)
in the highest-resolution bin are met.

For reference, CORRECT for a ~2.0 A PTP1B dataset with 150,000 unique reflections 
takes ~23 s.

## Example usage:

```
python xds_iter.py --images "/path/to/images/mydata_1_00???.cbf" 

(Don't forget the quotes around the images argument!)
(Run without any arguments to see all options)
```

## Conditions to run:

### Software requirements:

```
* Python
* XDS
* generate_XDS.INP script
* Diffraction images with a consistent naming convention
```

### Additional requirements:

