#TODO: Fix longest water being set to NULL when long transects exit the watershed.

# import libraries 
import arcpy

class River:
    arcpy.CheckOutExtension("Spatial")
    arcpy.env.overwriteOutput = True

    def __init__(self, workspace, river_name, river_feature, dem) -> None:
        """Create a River object

        Args:
            workspace (str): Path to gdb
            river_name (str): Name for output
            river_feature (str): Name of river polygon in gdb
            dem (str): Name of DEM in gdb
        """
        self.workspace = workspace
        arcpy.env.workspace = workspace
        self.river_feature = river_feature
        self.dem = dem 
        self.river = river_name

        # set local variables for geoprocessing
        self.polygon = f'{self.river}_polygon'
        self.polygon_dissolve = f'{self.river}_polygon_dissolve'
        self.centerline = f'{self.river}_centerline'
        self.splitpoints = f'{self.river}_splitpoints'
        self.splitline = f'{self.river}_splitline'
        self.points_final = f'{self.river}_points_final'
        self.transects = f'{self.river}_transects'
        self.transects_clipped = f'{self.river}_transects_clipped'
        self.transects_sp = f'{self.river}_transect_sp'
        self.elevation = f'{self.river}_elevation'
        self.output_data = f'{self.river}_data'
        self.dtm = f'dtm_{self.river}'
        self.side_points = f'{self.river}_side_points'
        self.side_points_elev = f'{self.river}_side_points_elev'
        self.side_points_elev_crs = f'{self.river}_side_points_elev_crs'
        self.point_distance = 10
        self.transect_distance = self.point_distance/2+0.01
        self.transect_length = 300
        self.distance_tupl = (0, 2, 4, 6, 8, 10, 12, 14, 16, 18, 20)
        
    def data_import(self, feature_class, field_names='*', new_names=None) -> dict[int: any]: 
        """Reads data from a feature class

        Args:
            feature_class (str): Name of fc in gdb or path
            field_names (tuple[str]): Field names to import. '*' returns all. First item needs to be a uniqe ID like OBJECTID
            new_names (tuple[str]): Field name aliases to use after import

        Returns:
            dict[int: any]: A nested dict with ID as key and field value as value
        """
        if new_names == None:
            new_names = [x.name for x in arcpy.ListFields(feature_class)]
        data = {}
        self.spatial_ref = arcpy.Describe(feature_class).spatialReference
        with arcpy.da.SearchCursor(feature_class, field_names) as cursor:
            for row in cursor:
                row_dict = {}
                for i in range(len(new_names)):
                    row_dict[new_names[i]] = row[i]
                data[row[0]] = row_dict
        return data
    
    def data_export(self, feature_class, fields) -> None: 
        """Export data back to feature class in gdb.
        Exports data from self.data.
        self.export() can be called to export all fields.

        Args:
            feature_class (str): Name of fc to be created
            fields (list[str]): Iterable with names of fields to be exported. Avoid protected field names
        """
        arcpy.management.CreateFeatureclass(arcpy.env.workspace, feature_class, 'POINT', '', '', '', self.spatial_ref)
        fields_list = []
        for row in self.data:
            if None not in self.data[row].values(): # find data point without None
                for key in fields:
                    if isinstance(self.data[row][key], int):
                        fields_list.append([key, 'LONG'])
                    elif isinstance(self.data[row][key], float):
                        fields_list.append([key, 'FLOAT'])
                break      
        arcpy.management.AddFields(feature_class, fields_list)
        insert_cursor = arcpy.da.InsertCursor(feature_class, fields)
        for row in self.data:
            insert_values = []
            missing_fields = []
            for field in fields:
                try:
                    insert_values.append(self.data[row][field])
                except:
                    missing_fields.append(field)
                    pass
            try:
                insert_cursor.insertRow(insert_values)
            except:
                print(f"Error in exporting data to point {self.data[row]['ID']} due to missing data in the following fields: {missing_fields}")
        del insert_cursor
        
    def calculate_length(self, point_a, point_b): # finds length of river between two points
        length = 0 # counting variable
        switch = 1 # switch to reverse for loop
        if self.data[point_a]['River_Sequence'] > self.data[point_b]['River_Sequence']:
            switch = -1
        river = self.data[point_a]['River_Segment']
        for pos in self.data:
            if self.data[pos]['River_Segment'] == river and self.data[pos]['River_Sequence'] in \
            range(self.data[point_a]['River_Sequence'], self.data[point_b]['River_Sequence']+switch, switch):
                if (self.data[pos]['River_Sequence'] == self.data[point_a]['River_Sequence']) or \
                (self.data[pos]['River_Sequence'] == self.data[point_b]['River_Sequence']):
                    length += self.data[pos]['Length']/2
                else: 
                    length += self.data[pos]['Length']
        return(length)
        
    def calculate_gradient(self, river): # finds gradient from downstream point
        sequences = self.sort_sequence(river)
        for i in range(len(sequences)-1):
            self.data[sequences[i][1]]['Gradient'] = ((self.data[sequences[i][1]]['Elevation'] - self.data[sequences[i+1][1]]['Elevation']) / self.calculate_length(sequences[i][1], sequences[i+1][1])) * 100
        
    def add_xsection_data(self, river) -> None:
        """Method that calls self.calc_xsection_area() and self.calc_xsection_slope()
        on each point in each river segment.

        Args:
            river (int): Number representing the river segment
        """
        sequences = self.sort_sequence(river)
        for i in range(1, len(sequences)):
            try:
                self.calc_xsection_area(sequences[i][1])
                self.calc_xsection_slope(sequences[i][1])
            except:
                pass
    
    
    def sort_sequence(self, river) -> list[dict]:
        """Sorting method that sorts points in a river segment from upstream to downstrem.

        Args:
            river (int): Number representing the river segment

        Returns:
            list[int, int]: Returns a nested list[sequence, id]
        """
        sequences = [(self.data[x]['River_Sequence'], x) for x in self.data if self.data[x]['River_Segment'] == river]
        if self.data[sequences[0][1]]['Elevation'] < self.data[sequences[len(sequences)-1][1]]['Elevation']:
            sequences.sort(reverse=True, key=lambda x:x[0])    
        else:
            sequences.sort(key=lambda x:x[0])
        return sequences
    
    def add_no_data(self, fields) -> None:
        """Adds type None to all points in self.data that doesn't have a value for the specific field

        Args:
            fields (tupel[str]): Takes an iterable of strings with fieldnames to assign NoData for
        """
        for field in fields:
            for row in self.data:
                if field not in self.data[row]:
                    self.data[row][field] = None
                    
    
    def find_critical_points(self, q, slope=None, dynamic=False) -> dict[int: int]: #Kan jeg kode slope dynamisk ut i fra slope i lengderetningen?
        """A method that selects candidate critical points based on water can reach.
        Uses a dict[list] called self.crit as input, as well as q

        Args:
            q (int): Number representing the discharge scenario
            slope (int): slope in cross-section that selects points as critical

        Returns:
            dict[int: int]: A dict with IDs for the points on the river bank that can be critical as key, and critical percentage as value
        """
        def get_crit_value(point, distance, side):
            max_elevation = max([self.data[point][f'river_side_{x}_{side}'] for x in self.distance_tupl[:self.distance_tupl.index(distance)+1]])
            crit_value = ((max_elevation - self.data[point]['Elevation']) / self.data[point][f'Q{q}_wse_diff']) * 100
            return crit_value
            
        self.crit = {}
        all_points = [f'{dist}_{side}' for side in ('r', 'l') for dist in self.distance_tupl]
        
        if slope != None or dynamic:
            for point in self.data:
                if dynamic:
                    if self.data[point]['Gradient'] == None:
                        slope = float('inf')
                    else:
                        slope = self.data[point]['Gradient']
                crit = []
                for i, dist in enumerate(self.distance_tupl):
                    if dist < self.distance_tupl[-1]:
                        next_dist = self.distance_tupl[i+1]
                        for side in ('r', 'l'):
                            if self.data[point][f'slope_{dist}_{next_dist}_{side}'] != None and self.data[point][f'slope_{dist}_{next_dist}_{side}'] < slope:
                                crit.append(f'{dist}_{side}')
                self.crit[point] = crit
            actual_crit = {}
            for x in self.crit:
                temp_lst = []
                for y in self.crit[x]:
                    if self.data[x][f'Q{q}_wse_diff'] != None and self.data[x][f'longest_water_Q{q}_{y[-1]}'] != None and self.data[x][f'longest_water_Q{q}_{y[-1]}'] >= int(y[:-2]):
                        if self.data[x][f'river_side_{y}'] - self.data[x]['Elevation'] < self.data[x][f'Q{q}_wse_diff']:
                            temp_lst.append(y)
                if len(temp_lst) > 0:
                    actual_crit[x] = temp_lst
        else:
            actual_crit = {}
            for x in self.data:
                temp_lst = []
                for y in all_points:
                    if self.data[x][f'Q{q}_wse_diff'] != None and self.data[x][f'longest_water_Q{q}_{y[-1]}'] != None and self.data[x][f'longest_water_Q{q}_{y[-1]}'] >= int(y[:-2]):
                        if self.data[x][f'river_side_{y}'] - self.data[x]['Elevation'] < self.data[x][f'Q{q}_wse_diff']:
                            temp_lst.append(y)
                if len(temp_lst) > 0:
                    actual_crit[x] = temp_lst
                    
        
        actual_crit_short = {}
        for x in actual_crit:
            for side in ('r', 'l'):
                tmp_lst = []
                for y in actual_crit[x]:
                    if y[-1] == side:
                        tmp_lst.append(int(y[:-2]))
                if len(tmp_lst) > 0:
                    if x not in actual_crit_short:
                        actual_crit_short[x] = [f'{max(tmp_lst)}_{side}']
                    else:
                        actual_crit_short[x] += [f'{max(tmp_lst)}_{side}']
                        
        crit_points = {}
        for point in actual_crit:
            sides = set([x[-1] for x in actual_crit[point]])
            for side in sides:
                if side == 'r':
                    distances = [int(x[:-2]) for x in actual_crit[point] if x[-1] == 'r']
                    with arcpy.da.SearchCursor(self.side_points_elev, ['OBJECTID', 'side', 'distance'], f'orig_id = {point}') as cursor:
                        for row in cursor:
                            if row[1][0] == side and row[2] in distances:
                                crit_value_r = get_crit_value(point, row[2], row[1][0])
                                crit_points[row[0]] = crit_value_r
                elif side == 'l':
                    distances = [int(x[:-2]) for x in actual_crit[point] if x[-1] == 'l']
                    with arcpy.da.SearchCursor(self.side_points_elev, ['OBJECTID', 'side', 'distance'], f'orig_id = {point}') as cursor2:
                        for row2 in cursor2:
                            if row2[1][0] == side and row2[2] in distances:
                                crit_value_l = get_crit_value(point, row2[2], row2[1][0])
                                crit_points[row2[0]] = crit_value_l
        return crit_points     
                                    
    def add_river_bank(self, raster=None) -> None:
        """A method for generating points in the cross-section of the river.
        Takes no args, but uses variables stored in the object self.
        Exports a feature class with points named 'river name' + side_points.
        Optionally exports a feature class with points with other crs

        Args:
            raster (str, optional): Name or path to raster for reprojection. Defaults to None.
        """
        # Left and right can sometimes be on the wrong side depending on how the splitlines were created.
        self.distances = {distance: (f'river_side_{distance}_r', f'river_side_{distance}_l') for distance in sorted(self.distance_tupl)}
        id_points_dic2 = {}
        trans = self.data_import(self.transects, ('ORIG_FID', 'Shape@'), ('ORIG_FID', 'Shape@'))
        center = self.data_import(self.splitline, ('OBJECTID', 'Shape@'), ('OBJECTID', 'Shape@'))
        poly = self.data_import(self.polygon_dissolve, ('OBJECTID', 'Shape@'), ('OBJECTID', 'Shape@'))
        # poly = self.data_import(self.river_feature, ('OBJECTID', 'Shape@'), ('OBJECTID', 'Shape@'))
        for row in trans:
            startpoint_dic = {}
            side_dic = {}
            points_dic = {}
            side_dic['left'], side_dic['right'] = trans[row]['Shape@'].cut(center[row]['Shape@'])
            right_start = side_dic['right'].lastPoint.X == side_dic['left'].firstPoint.X and side_dic['right'].lastPoint.Y == side_dic['left'].firstPoint.Y
            for side in side_dic:
                points = {}
                diff = side_dic[side].difference(poly[1]['Shape@'])
                if side == 'left':
                    if not right_start:
                        diff_line = arcpy.Polyline(arcpy.Array([diff.lastPoint, side_dic['left'].firstPoint]), self.spatial_ref)
                    else:
                        diff_line = arcpy.Polyline(arcpy.Array([diff.firstPoint, side_dic['left'].lastPoint]), self.spatial_ref)
                    for d in self.distance_tupl:
                        pos = diff_line.positionAlongLine(d).centroid
                        points[d] = (pos.X, pos.Y)
                else:
                    if not right_start:
                        diff_line = arcpy.Polyline(arcpy.Array([diff.firstPoint, side_dic['right'].lastPoint]), self.spatial_ref)
                    else:
                        diff_line = arcpy.Polyline(arcpy.Array([diff.lastPoint, side_dic['right'].firstPoint]), self.spatial_ref)
                    for d in self.distance_tupl:
                        pos = diff_line.positionAlongLine(d).centroid
                        points[d] = (pos.X, pos.Y)
                points_dic[side] = points
            id_points_dic2[row] = points_dic
            
        arcpy.management.CreateFeatureclass(arcpy.env.workspace, self.side_points, 'POINT', '', '', '', self.spatial_ref)
        fields = (['orig_id', 'SHORT'], ['distance', 'SHORT'], ['side', 'TEXT'])
        arcpy.management.AddFields(self.side_points, fields)
        with arcpy.da.InsertCursor(self.side_points, ('orig_id', 'side', 'distance', 'SHAPE@XY')) as in_cursor:
            for id_point in id_points_dic2:
                for side in id_points_dic2[id_point]:
                    for distance in id_points_dic2[id_point][side]:
                        in_cursor.insertRow((id_point, side, distance, id_points_dic2[id_point][side][distance]))
                        
        arcpy.sa.ExtractValuesToPoints(self.side_points, self.dem, self.side_points_elev)
        if raster:
            arcpy.management.Project(self.side_points_elev, self.side_points_elev_crs, arcpy.Describe(raster).spatialReference)
        
        with arcpy.da.SearchCursor(self.side_points_elev, ['orig_id', 'side', 'distance', 'RASTERVALU']) as cursor:
            for row in cursor:
                self.data[row[0]][f'river_side_{row[2]}_{row[1][0]}'] = row[3]
                
    def add_river_bank2(self, raster=None) -> None: #Latest version
        """A method for generating points in the cross-section of the river.
        Takes no args, but uses variables stored in the object self.
        Exports a feature class with points named 'river name' + side_points.
        Optionally exports a feature class with points with other crs

        Args:
            raster (str, optional): Name or path to raster for reprojection. Defaults to None.
        """
        # Left and right can sometimes be on the wrong side depending on how the splitlines were created.
        self.distances = {distance: (f'river_side_{distance}_r', f'river_side_{distance}_l') for distance in sorted(self.distance_tupl)}
        id_points_dic2 = {}
        trans = self.data_import(self.transects, ('ORIG_FID', 'Shape@'), ('ORIG_FID', 'Shape@'))
        poly = self.data_import(self.polygon_dissolve, ('OBJECTID', 'Shape@'), ('OBJECTID', 'Shape@'))
        # poly = self.data_import(self.river_feature, ('OBJECTID', 'Shape@'), ('OBJECTID', 'Shape@'))
        for row in trans:
            startpoint_dic = {}
            side_dic = {}
            last_dic = {}
            points_dic = {}
            side_dic['left'] = arcpy.Polyline(arcpy.Array([trans[row]['Shape@'].centroid, trans[row]['Shape@'].firstPoint]), self.spatial_ref)
            last_dic['left'] = trans[row]['Shape@'].firstPoint
            side_dic['right'] = arcpy.Polyline(arcpy.Array([trans[row]['Shape@'].centroid, trans[row]['Shape@'].lastPoint]), self.spatial_ref)
            last_dic['right'] = trans[row]['Shape@'].lastPoint
            for side in side_dic:
                points = {}
                orientation = (side_dic[side].firstPoint.X - side_dic[side].lastPoint.X, side_dic[side].firstPoint.Y - side_dic[side].lastPoint.Y)
                side_dic[side] = side_dic[side].difference(poly[1]['Shape@'])
                if orientation[0] < 0:
                    first_point = min((p for sublist in side_dic[side] for p in sublist), key=lambda x: x.X)
                elif orientation[0] > 0:
                    first_point = max((p for sublist in side_dic[side] for p in sublist), key=lambda x: x.X)
                else:
                    if orientation[1] < 0:
                        first_point = min((p for sublist in side_dic[side] for p in sublist), key=lambda x: x.Y)
                    else:
                        first_point = max((p for sublist in side_dic[side] for p in sublist), key=lambda x: x.Y)
                side_dic[side] = arcpy.Polyline(arcpy.Array([first_point, last_dic[side]]), self.spatial_ref)
                for d in self.distance_tupl:
                    pos = side_dic[side].positionAlongLine(d).centroid
                    points[d] = (pos.X, pos.Y)                
                points_dic[side] = points
            id_points_dic2[row] = points_dic
            
        arcpy.management.CreateFeatureclass(arcpy.env.workspace, self.side_points, 'POINT', '', '', '', self.spatial_ref)
        fields = (['orig_id', 'SHORT'], ['distance', 'SHORT'], ['side', 'TEXT'])
        arcpy.management.AddFields(self.side_points, fields)
        with arcpy.da.InsertCursor(self.side_points, ('orig_id', 'side', 'distance', 'SHAPE@XY')) as in_cursor:
            for id_point in id_points_dic2:
                for side in id_points_dic2[id_point]:
                    for distance in id_points_dic2[id_point][side]:
                        in_cursor.insertRow((id_point, side, distance, id_points_dic2[id_point][side][distance]))
                        
        arcpy.sa.ExtractValuesToPoints(self.side_points, self.dem, self.side_points_elev)
        if raster:
            arcpy.management.Project(self.side_points_elev, self.side_points_elev_crs, arcpy.Describe(raster).spatialReference)
        
        with arcpy.da.SearchCursor(self.side_points_elev, ['orig_id', 'side', 'distance', 'RASTERVALU']) as cursor:
            for row in cursor:
                self.data[row[0]][f'river_side_{row[2]}_{row[1][0]}'] = row[3]      
    
    def calc_xsection_slope(self, point) -> None:
        """Calculates the slope between points on both sides of the river in percentage.
        The formula is (rise / run) * 100.
        Adds a field in self.data called slope_{distance from river}_{next distance}_{side}

        Args:
            point (int): ID of point in the river to have slope calculated
        """
        
        for i, dist in enumerate(self.distance_tupl):
            if dist < self.distance_tupl[-1]:
                next_dist = self.distance_tupl[i+1]
                for side in range(2): 
                    slope = (self.data[point][self.distances[next_dist][side]] - self.data[point][self.distances[dist][side]]) / (next_dist - dist) * 100
                    if side == 0:
                        self.data[point][f'slope_{dist}_{next_dist}_r'] = slope
                    else:
                        self.data[point][f'slope_{dist}_{next_dist}_l'] = slope                              
                        

    def calc_xsection_area(self, point) -> None:
        """Calculates area of cross-section for both sides of the river.
        Adds fields for both sides of the river to self.data
    
        Args:
            point (int): ID of point in the river to have area calculated
        """
        base = self.data[point]['Elevation']
        for side in range(2):
            area = 0
            for i, dist in enumerate(self.distance_tupl):
                if dist < self.distance_tupl[-1]:
                    next_dist = self.distance_tupl[i+1]
                    height1 = (self.data[point][self.distances[next_dist][side]] - base)
                    height2 = (self.data[point][self.distances[dist][side]] - base)
                    area += ((height1 + height2) / 2) * (next_dist - dist)
            if side == 0:
                self.data[point][f'slope_area_r'] = area
            else:
                self.data[point][f'slope_area_l'] = area
                    
    
    def full_analysis(self) -> None:
        """Runs the full analysis with all geoprocessing.
        Generates all the data in self.data
        """
        print("Running geoprocessing tools")
        # arcpy.analysis.Select(self.river_feature, self.polygon, "objtype = 'ElvBekk'") 
        arcpy.management.Dissolve(self.river_feature, self.polygon_dissolve)
        # arcpy.management.Dissolve(self.polygon, self.polygon_dissolve)
        arcpy.topographic.PolygonToCenterline(self.polygon_dissolve, self.centerline)
        # arcpy.topographic.PolygonToCenterline(self.river_feature, self.centerline)
        arcpy.management.GeneratePointsAlongLines(self.centerline, self.splitpoints, 'DISTANCE', f'{self.point_distance} meters')
        arcpy.management.SplitLineAtPoint(self.centerline, self.splitpoints, self.splitline, '0,1 meters')
        arcpy.management.GeneratePointsAlongLines(self.splitline, self.points_final, 'PERCENTAGE', Percentage=50)
        arcpy.management.GenerateTransectsAlongLines(self.splitline, self.transects, f'{self.point_distance/2+0.01} meters', f'{self.transect_length} meters')
        arcpy.analysis.Clip(self.transects, self.polygon_dissolve, self.transects_clipped)
        # arcpy.analysis.Clip(self.transects, self.river_feature, self.transects_clipped)
        arcpy.management.MultipartToSinglepart(self.transects_clipped, self.transects_sp)
        arcpy.sa.ExtractValuesToPoints(self.points_final, self.dem, self.elevation)
        
        
        print("importing data")
        self.data = self.data_import(self.points_final, ('OBJECTID', 'Shape@XY', 'ORIG_FID_1', 'ORIG_SEQ', 'SHAPE_Length'), \
                                                    ('ID', 'Shape@XY', 'River_Segment', 'River_Sequence', 'Length' ))
        
        arcpy.sa.ExtractMultiValuesToPoints(self.points_final, [['wse100', 'wse100'], ['wse5', 'wse5']])
    
        # add elevation to data table
        print("Adding elevation")
        with arcpy.da.SearchCursor(self.elevation, ['RASTERVALU', 'ORIG_FID']) as cursor:
            for row in cursor:
                self.data[row[1]]['Elevation'] = row[0]
                        
        print("Adding water surface elevation difference")
        with arcpy.da.SearchCursor(self.points_final, ['wse100', 'wse5', 'ORIG_FID']) as cursor:
            for row in cursor:
                if row[0]:
                    self.data[row[2]]['Q100_wse_diff'] = row[0] - self.data[row[2]]['Elevation']
                else:
                    self.data[row[2]]['Q100_wse_diff'] = None
                if row[1]:
                    self.data[row[2]]['Q5_wse_diff'] = row[1] - self.data[row[2]]['Elevation']
                else:
                    self.data[row[2]]['Q5_wse_diff'] = None
         
        self.distance_fields = tuple([f'river_side_{x}_{y}' for x in self.distance_tupl for y in ('r', 'l')]) + tuple([f'slope_{x}_{self.distance_tupl[i+1]}_{y}' for i ,x in enumerate(self.distance_tupl) if x < self.distance_tupl[-1] for y in ('r', 'l')])
        print("Adding NoData")
        self.add_no_data(('Gradient', 'River_Segment', 'slope_area_r', 'slope_area_l', 'Q100_wse_diff', 'Q5_wse_diff', 'longest_water_Q5_l', 'longest_water_Q5_r', 'longest_water_Q100_r', 'longest_water_Q100_l') + (self.distance_fields))

        self.add_river_bank2()
        
        
        river_set = set() # set for looping through rivers
        for row in self.data:
            river_set.add(self.data[row]['River_Segment'])
        num_rivers = len(river_set)
        for count, river in enumerate(river_set):
            print(f"Adding gradient in river {count+1}/{num_rivers}")    
            self.calculate_gradient(river)
            print(f"Adding xsection in river {count+1}/{num_rivers}") 
            self.add_xsection_data(river)
        
        print("Adding furthest water level from center")
        for point in self.data:
            for q in ('Q100_wse_diff', 'Q5_wse_diff'):
                if self.data[point][q] != None:
                    for side in ('r', 'l'):
                        for i, d in enumerate(self.distance_tupl):
                            if self.data[point][f'river_side_{d}_{side}']:
                                w_level = self.data[point]['Elevation'] + self.data[point][q]
                                if self.data[point][f'river_side_{d}_{side}'] > w_level:
                                    if d == 0:
                                        self.data[point][f'longest_water_{q[:-9]}_{side}'] = d
                                        break
                                    else:
                                        self.data[point][f'longest_water_{q[:-9]}_{side}'] = self.distance_tupl[i-1]
                                        break 
                                elif d == self.distance_tupl[-1]:
                                    self.data[point][f'longest_water_{q[:-9]}_{side}'] = d                            

                else:
                    self.data[point][f'longest_water_{q[:-9]}_r'] = None     
                    self.data[point][f'longest_water_{q[:-9]}_l'] = None   
        


                  
    def export(self) -> None:
        """Exports all fields found in arbitrary point in self.data. ID 1 as default
        """
        print("Exporting data")
        fields = [x for x in self.data[1]]
        self.data_export(self.output_data, fields)
    
    
    
if __name__ == "__main__":
    river = River("arguments")
    river.full_analysis()
    river.export() 

    
arcpy.CheckInExtension("Spatial")