from river_geometry import River as River_dic
from critical_paths import Flood_path
from parameter_statistics import Stats
import time

"""
Hardware:
This program was tested a computer with a 
Intel64 Family 6 Model 154 Stepping 3, GenuineIntelprocessor with a maximum clock frequency of 2300.0 MHz 
with 14 physical cores, 20 logical cores and 31.75GB of RAM, using the Operating System Windows 10.0.22631.

Software:
ArcGIS Pro 3.3.0
Rasterio 1.3.10
Python 3.11.8

"""

workspace = 'path'
river_name = 'path'
side_points = 'path'
dem = 'dem'
dem_res = '1'
comp_flow = '1'
q = 100
transect_space = 4
transect_width = 80
transect_point_space = 4
distances = tuple(x for x in range(0, transect_width+1, transect_point_space))


for q in (5, 100):
    for i in range(5):
        river = River_dic(workspace, river_name, 'river_polygon', dem)
        river.distance_tupl = distances
        river.point_distance = transect_space
        geom_st = time.perf_counter()
        river.full_analysis()
        geom_et = time.perf_counter()
        cp = river.find_critical_points(q)
        flood_test = Flood_path(workspace, 'flow_raster', side_points)
        cp_st = time.perf_counter()
        all = flood_test.import_data(cp)
        all_analyzed = flood_test.analyze(all, duplicate_paths=True)
        cp_et = time.perf_counter()
        geom_tt = geom_et - geom_st
        cp_tt = cp_et - cp_st
        out_name = f"final_cp_paths_{q}"
        flood_test.export(all_analyzed, out_name)
        stats = Stats(river, flood_test, out_name, geom_tt, cp_tt)
        stats.calculate()