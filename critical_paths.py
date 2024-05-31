import arcpy
import rasterio

class Flood_path:
    
    def __init__(self, workspace: str, raster: str, point_fc: str) -> None:
        """Create a flood-path object for identification of critical points.

        Args:
            workspace (str): Path to gdb
            raster (str): Name or path to raster with D8 and vector layers
            point_fc (str): Name of fc in gdb with cross-sectional points
        """
        arcpy.env.overwriteOutput = True
        arcpy.env.workspace = workspace
        self.f = rasterio.open(raster)
        self.f_arr = self.f.read()
        self.point_fc = point_fc
        self.spatial_ref = arcpy.Describe(self.point_fc).spatialReference
        self.num_crit = 0

    def __flow_dir(self, index: tuple[int, int], raster: any) -> tuple[tuple[int, int], int]:
        """Private method called by self.analyze() that finds next index in raster based on flow direction.

        Args:
            index (tuple[int, int]): x- and y-index reference in raster matrix.
            raster (any): Numpy array with three dimensions

        Returns:
            tuple[tuple[int, int], int]: The next index for processing, as well as the target value.
        """
        direction = raster[0, index[0], index[1]]
        col = 0
        row = 0
        if direction == 1:
            row = 0
            col = 1
        elif direction == 2:
            row = 1
            col = 1
        elif direction == 4:
            row = 1
            col = 0
        elif direction == 8:
            row = 1
            col = -1
        elif direction == 16:
            row = 0
            col = -1
        elif direction == 32:
            row = -1
            col = -1
        elif direction == 64:
            row = -1
            col = 0
        elif direction == 128:
            row = -1
            col = 1
        elif direction < 1 or direction > 128:
            return (index[0]+row, index[1]+col), 4
        new_row = index[0]+row
        new_col = index[1]+col
        return (new_row, new_col), raster[1, new_row, new_col]



    def import_data(self, crit_points=None) -> dict[int: tuple[int, int]]:
        """Imports data and converts latlong points to array index

        Args:
           crit_points (dict[int: int], optional): A dict of points the be used, with critical percentage as value. Defaults to None = all points.
        
        Returns:
            dict[int: tuple[int, int]]: Key is ID of point, value is x an y.
        """
        self.crit_points = crit_points
        output_points = {}
        if crit_points != None:
            with arcpy.da.SearchCursor(self.point_fc, ['Shape@XY', 'OBJECTID'], f"OBJECTID IN {tuple(crit_points)}") as cursor:
                for row in cursor:
                    output_points[row[1]] = row[0]
            output_points = {x: self.f.index(output_points[x][0], output_points[x][1]) for x in output_points}
        else:
            with arcpy.da.SearchCursor(self.point_fc, ['Shape@XY', 'OBJECTID']) as cursor:
                for row in cursor:
                    output_points[row[1]] = row[0]
            output_points = {x: self.f.index(output_points[x][0], output_points[x][1]) for x in output_points}
        return output_points


    def analyze(self, points: dict[int: tuple[int, int]], duplicate_paths: bool = False, first_point: bool = False) -> dict[int: arcpy.Array, int]:
        """Evaluates candidate critical points by their downstream flow path.
        
        Args:
            points (dict[int: tuple[int, int]]): Output from import method
            duplaicate_points (bool, optional): Whether or not to break when a path is already marked as critical. Defaults to false.
            first_point (bool, optional): First point that flows into a critical path is used, not most critical.

        Returns:
            dict[int: (arcpy.Array, int)]: Key: objectID of critical point on riverbank. Value: tuple with arcpy array with flow path points and id of point on centerline.
        """
        def get_duplicate_key(paths, point):
            for key, value in paths.items():
                if point in value[0]:
                    return key
                # otherwise return None

        length = len(points)
        paths = {}
        for i, p in enumerate(points):
            if i < length:
                print(f"Analyzing point {i} of {length}", end="\r")
            else:
                print(f"Analyzing point {i} of {length}")
            point = points[p]
            path = [point]
            crit_points = []
            target = self.f_arr[1, point[0], point[1]]
            critical = target in (1, 2)
            while True:
                if target == 1 or target == 2:
                    critical = True
                    try:
                        crit_points.append(point)
                    except:
                        crit_points.append(points[p])
                if not (first_point or duplicate_paths):
                    idx = get_duplicate_key(paths, path[-1])
                    if idx:
                        if paths[idx][1] > self.crit_points[p]:
                            first_crit_idx = paths[idx][0].index(paths[idx][2][0])
                            last_crit_idx = paths[idx][0].index(paths[idx][2][-1])
                            current_idx = paths[idx][0].index(path[-1])
                            if current_idx < last_crit_idx:
                                paths[p] = [path + paths[idx][0][current_idx:], self.crit_points[p], crit_points + [x for x in paths[idx][0][current_idx:] if x in paths[idx][2]]]
                                # crit_keys_reversed.insert(0, p)
                            elif critical:
                                paths[p] = [path, self.crit_points[p], crit_points]
                                # crit_keys_reversed.insert(0, p)
                                break
                            else:
                                break
                            if first_crit_idx <= current_idx:
                                paths[idx][0] = paths[idx][0][:current_idx+1]
                                paths[idx][2] = [x for x in paths[idx][2] if x in paths[idx][0]]
                            else:    
                                del paths[idx]
                                # crit_keys_reversed.remove(idx)
                        elif critical:
                            paths[p] = [path, self.crit_points[p], crit_points]
                            # crit_keys_reversed.insert(0, p)
                        break
                elif not duplicate_paths:
                    if any(point in paths[x][0] for x in paths):
                        if critical:
                            paths[p] = [path, self.crit_points[p], crit_points]
                            # crit_keys_reversed.insert(0, p)
                        break
                if target == 4:
                    if critical:
                        paths[p] = [path, self.crit_points[p], crit_points]
                        # crit_keys_reversed.insert(0, p)
                    break
                if target == 3:
                    if critical:
                        paths[p] = [path, self.crit_points[p], crit_points]
                        # crit_keys_reversed.insert(0, p)
                    break
                point, target = self.__flow_dir(path[-1], self.f_arr)
                path.append(point)

        self.crit_num = len(paths)
        paths = {x: [[self.f.xy(y[0], y[1]) for y in paths[x][0]], paths[x][1]] for x in paths}
        paths_points = {x: [[arcpy.Point(y[0], y[1]) for y in paths[x][0]], paths[x][1]] for x in paths}
        paths_array = {x: [arcpy.Array(paths_points[x][0]), paths_points[x][1]] for x in paths_points}
        
        # for point in paths_array:
        #     with arcpy.da.SearchCursor(self.point_fc, ['orig_id', 'RASTERVALU'], f'OBJECTID = {point}') as cursor:
        #         for row in cursor:
        #             paths_array[point] = (paths_array[point], (row[0], row[1]))
        return paths_array

    def export(self, input: dict[int: (arcpy.Array, int)], output: str) -> None:
        """Exports critical points to feature class in gdb.
        The field 'point_id' referes to point where flow starts.

        Args:
            input (dict[int: (arcpy.Array, int)]): Output from self.analyze()
            output (str): Name of fc to be exported
        """
        arcpy.management.CreateFeatureclass(arcpy.env.workspace, output, 'POLYLINE', '', '', '', self.spatial_ref)
        arcpy.management.AddFields(output, [['point_id', 'LONG'], ['crit_percent', 'SHORT']])
        with arcpy.da.InsertCursor(output, ['SHAPE@', 'point_id', 'crit_percent']) as in_cursor:
            for line in input:
                    in_cursor.insertRow([arcpy.Polyline(input[line][0]), line, input[line][1]])


if __name__ == '__main__':
    flood_test = Flood_path("arguments")
    candidates = flood_test.import_data('data')
    critical = flood_test.analyze(candidates)
    flood_test.export(critical)
    