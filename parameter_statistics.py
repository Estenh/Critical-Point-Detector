import os
import arcpy
from river_geometry import River
from critical_paths import Flood_path
import csv
from datetime import datetime


class Stats:
    def __init__(self, river: River, flood_path: Flood_path, filename: str, geom_time: float, cp_time: float) -> None:
        arcpy.env.workspace = river.workspace
        self.river = river
        self.flood_path = flood_path
        self.filename = filename
        self.geom_time = geom_time
        self.cp_time = cp_time
        self.results = {}
        self.results['name'] = filename
        self.results['time'] = datetime.now()
        self.results['geo_time'] = geom_time
        self.results['cp_time'] = cp_time
        
        
    def calc_percentage(self):
        total_candidate = len(self.flood_path.crit_points)
        total_critical = self.flood_path.crit_num
        percent = total_critical/total_candidate*100
        self.results['candidates'] = total_candidate
        self.results['critical'] = total_critical
        self.results['percent'] = percent
        print(f"Candidate points: {total_candidate}, Critical points: {total_critical}, {percent}%")
        return percent
    
    def calc_mean_crit(self):
        num = 0
        tot = 0
        with arcpy.da.SearchCursor(self.filename, ['crit_percent']) as cursor:
            for row in cursor:
                num += 1
                tot += row[0]
        self.results['mean_crit'] = tot/num
        print(f'Mean crit percentage: {tot/num}')
    
    def calc_accuracy(self):
        sel_build = arcpy.management.SelectLayerByLocation('fkb_bygning_omrade', 'INTERSECT', self.filename, '1 Meters')
        self.results['build_inter'] = sel_build[2]
        print(f'number of intersections is: {sel_build[2]}')
        arcpy.analysis.Intersect([self.filename, 'fkb_veg_omrade'], 'temp_roads')
        arcpy.management.Dissolve('temp_roads', 'temp_roads_diss')
        tot_len_road = 0
        with arcpy.da.SearchCursor('temp_roads_diss', ['Shape_Length']) as cursor:
            for row in cursor:
                tot_len_road += row[0]
        self.results['road_inter'] = tot_len_road
        print(f'Length of road affected is {tot_len_road} meters')
        arcpy.management.Delete('temp_roads')
        arcpy.management.Delete('temp_roads_diss')

    def write_stats(self):
        file_path = "stats.csv"
        file_exists = os.path.exists(file_path)
        file_empty = os.path.getsize(file_path) == 0 if file_exists else True

        
        with open("stats.csv", "a", newline="") as f:
            w = csv.DictWriter(f, self.results.keys())
            if not file_exists or file_empty:
                w.writeheader()
            w.writerow(self.results)                
    
    def calculate(self):
        print(f'Geometry took: {self.geom_time} sec, Crit_path took: {self.cp_time} sec.')
        self.calc_percentage()
        self.calc_accuracy()
        self.calc_mean_crit()
        self.write_stats()
