import arcpy
from arcpy.sa import *
arcpy.env.overwriteOutput = True
arcpy.env.workspace = 'path'



print('Setting environment variables')
dem = 'dem_05_2'
watershed = 'Regine_Kaldvella'
arcpy.env.snapRaster = dem
arcpy.env.extent = watershed
val_field = 'OBJECTID'

river_vec = 'kaldvella_alt_ws'
build_vec = 'fkb_bygning_omrade'
road_vec = 'fkb_veg_omrade'
data_extent = watershed

print('Creating fkb rasters')
river_ras = 'river_ras'
arcpy.conversion.PolygonToRaster(river_vec, val_field, river_ras)
binary_river = Reclassify(river_ras, 'value', RemapRange([[0, 9999999, 3]]))
build_ras = 'build_ras'
arcpy.conversion.PolygonToRaster(build_vec, val_field, build_ras)
binary_build = Reclassify(build_ras, 'value', RemapRange([[0, 9999999, 2]]))
binary_build_exp = Expand(binary_build, 1, 2)
road_ras = 'road_ras'
arcpy.conversion.PolygonToRaster(road_vec, val_field, road_ras)
binary_road = Reclassify(road_ras, 'value', RemapRange([[0, 9999999, 1]]))

print('Creating hydro rasters')
dem_fill = Fill(ExtractByMask(dem, data_extent))
dem_flow = FlowDirection(dem_fill)

print('Merging rasters')
binary_build_road = Con(IsNull(binary_build_exp), binary_road, binary_build_exp)
binary_build_road_river = Con(IsNull(binary_river), binary_build_road, binary_river)
comp_flow = Raster(arcpy.management.CompositeBands([dem_flow, binary_build_road_river]))
comp_flow.save("path.tif")

print('Deleting temporary rasters')
del binary_river, binary_road, dem_fill, dem_flow, binary_build_road, binary_build, binary_build_exp, comp_flow, binary_build_road_river, road_ras, build_ras, river_ras

