import arcpy
import numpy as np
import matplotlib.pyplot as plt


arcpy.env.workspace = 'path'

distances = [x for x in range(0, 21, 1)]
full_range = [y*x for x in (-1, 1) for y in distances]
full_range.append(0)
final_dist = sorted(full_range)

def return_value(id, value):
    return arr[np.where(arr['OBJECTID'] == id)[0][0]][value]


fc = 'path'

# arr = arcpy.da.FeatureClassToNumPyArray('test_data', '*', skip_nulls=True)
arr = arcpy.da.FeatureClassToNumPyArray(fc, [fld.name for fld in arcpy.ListFields(fc) if fld.name != arcpy.Describe(fc).shapeFieldName and fld.name not in ('sinuosity', 's_turn')], skip_nulls=True)

# point = 755
point = 406

# width = return_value(point, 'Width')/2
width = 2

crit = arr[np.where((arr['Elevation'] > arr['river_side_2_r']) & (arr['Elevation'] > arr['river_side_2_l']))]

x = []
for i, d in enumerate(final_dist):
    if i < len(distances):
        x.append(d-width)
    elif i == len(distances):
        x.append(d)
    else:
        x.append(d+width)

y = []
for i in range(len(distances)-1, -1, -1):
    y.append(return_value(point, f'river_side_{distances[i]}_l'))
y.append(return_value(point, 'Elevation'))
for d in distances:
    y.append(return_value(point, f'river_side_{d}_r'))


            
xpoints = np.array(x)
ypoints = np.array(y)

# plt.text(-9, return_value(point, 'Elevation'), f'Left area = {"%.1f" % round(return_value(point, "slope_area_l"), 1)}m2', fontsize = 10)
# plt.text(3, return_value(point, 'Elevation'), f'Right area = {"%.1f" % round(return_value(point, "slope_area_r"),1)}m2', fontsize = 10)
plt.plot(xpoints, ypoints, color='red', label='River bank')
plt.plot([- width, 0, width], [return_value(point, 'river_side_0_l'), return_value(point, 'Elevation'), return_value(point, 'river_side_0_r')], color='blue', linewidth=2, label='River')
plt.axhline(y=return_value(point, 'Q100_wse_diff')+return_value(point, 'Elevation'), color='g', linestyle='dashed', label='Q100 wse')
plt.axhline(y=return_value(point, 'Q5_wse_diff')+return_value(point, 'Elevation'), color='y', linestyle='dashed', label='Q5 wse')
plt.legend(loc='upper left', fontsize='xx-large')
plt.xlabel('Width (m)')
plt.ylabel('Elevation (m)')
plt.show()




# 785 - 775

