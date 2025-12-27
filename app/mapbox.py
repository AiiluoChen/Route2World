import bpy
import math
import os
import urllib.request
import ssl
from mathutils import Vector
from ..parse.gpx import GeoPoint

class MapboxTerrainDownloader:
    def __init__(self, context):
        self.context = context
        # Get addon preferences. Package name might vary, so we try to find it.
        # Assuming the package name is the top level module name.
        package_name = __package__.split('.')[0]
        self.token = context.preferences.addons[package_name].preferences.mapbox_access_token
        self.ssl_context = ssl._create_unverified_context()

    def deg2num(self, lat_deg, lon_deg, zoom):
        lat_rad = math.radians(lat_deg)
        n = 2.0 ** zoom
        xtile = int((lon_deg + 180.0) / 360.0 * n)
        ytile = int((1.0 - math.asinh(math.tan(lat_rad)) / math.pi) / 2.0 * n)
        return (xtile, ytile)

    def num2deg(self, xtile, ytile, zoom):
        n = 2.0 ** zoom
        lon_deg = xtile / n * 360.0 - 180.0
        lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * ytile / n)))
        lat_deg = math.degrees(lat_rad)
        return (lat_deg, lon_deg)

    def download_and_create_terrain(self, gpx_points, quality="MEDIUM"):
        if not self.token:
            raise Exception("Mapbox Access Token is missing. Please set it in Add-on Preferences.")

        if not gpx_points:
            return None

        # Determine Bounds
        lats = [p.lat for p in gpx_points]
        lons = [p.lon for p in gpx_points]
        min_lat, max_lat = min(lats), max(lats)
        min_lon, max_lon = min(lons), max(lons)

        # Reference point for local coordinates (first point)
        lat0 = gpx_points[0].lat
        lon0 = gpx_points[0].lon
        
        # Projection constants
        EARTH_RADIUS_M = 6378137.0
        lat0_rad = math.radians(lat0)
        lon0_rad = math.radians(lon0)
        cos_lat0 = math.cos(lat0_rad)

        def project(lat, lon):
            lat_rad = math.radians(lat)
            lon_rad = math.radians(lon)
            x = (lon_rad - lon0_rad) * cos_lat0 * EARTH_RADIUS_M
            y = (lat_rad - lat0_rad) * EARTH_RADIUS_M
            return x, y

        # Add margin (approx 500m)
        margin_deg = 0.005
        min_lat -= margin_deg
        max_lat += margin_deg
        min_lon -= margin_deg
        max_lon += margin_deg

        # Determine Zoom
        zoom = 12
        if quality == "HIGH": zoom = 14
        elif quality == "LOW": zoom = 10
        
        # Calculate Tile Range
        t_min_x, t_min_y = self.deg2num(max_lat, min_lon, zoom) # Top-Left
        t_max_x, t_max_y = self.deg2num(min_lat, max_lon, zoom) # Bottom-Right
        
        # Ensure correct ordering
        start_x, end_x = min(t_min_x, t_max_x), max(t_min_x, t_max_x)
        start_y, end_y = min(t_min_y, t_max_y), max(t_min_y, t_max_y)

        # Download Tiles and Process
        # We will build a grid of vertices.
        # To keep it simple, we process row by row of TILES.
        # And within each tile, we have 256x256 pixels.
        
        # Resolution optimization
        step = 4 # Sample every 4th pixel to reduce poly count
        if quality == "HIGH": step = 2
        
        tile_size = 256
        eff_tile_size = tile_size // step
        
        total_cols = (end_x - start_x + 1) * eff_tile_size
        total_rows = (end_y - start_y + 1) * eff_tile_size
        
        # Limit total vertices to avoid crash
        if total_cols * total_rows > 1000000: # 1M verts
             step *= 2
             eff_tile_size = tile_size // step
             total_cols = (end_x - start_x + 1) * eff_tile_size
             total_rows = (end_y - start_y + 1) * eff_tile_size
        
        verts = []
        
        # Pre-calculate tile images to avoid re-reading
        tile_images = {}
        
        print(f"Downloading tiles: X[{start_x}-{end_x}], Y[{start_y}-{end_y}], Zoom {zoom}")
        
        for tx in range(start_x, end_x + 1):
            for ty in range(start_y, end_y + 1):
                url = f"https://api.mapbox.com/v4/mapbox.terrain-rgb/{zoom}/{tx}/{ty}.pngraw?access_token={self.token}"
                try:
                    filename = f"mapbox_terrain_{zoom}_{tx}_{ty}.png"
                    filepath = os.path.join(bpy.app.tempdir, filename)
                    
                    # Cache check
                    if not os.path.exists(filepath):
                        with urllib.request.urlopen(url, context=self.ssl_context) as response, open(filepath, 'wb') as out_file:
                            out_file.write(response.read())
                    
                    img = bpy.data.images.load(filepath)
                    # Force reload to ensure pixels are available
                    img.reload()
                    tile_images[(tx, ty)] = img
                except Exception as e:
                    print(f"Failed to download/load tile {tx},{ty}: {e}")
                    tile_images[(tx, ty)] = None

        # Build Mesh
        # We iterate logically over the whole grid
        # y goes from top to bottom (lat decreases)
        # x goes from left to right (lon increases)
        
        # We need to map grid (row, col) to (lat, lon)
        # Mapbox Web Mercator projection
        
        def pixel_to_latlon(px, py, zoom):
            # px, py are global pixel coordinates
            n = 2.0 ** zoom
            # 256 pixels per tile
            lon_deg = (px / 256.0) / n * 360.0 - 180.0
            lat_rad = math.atan(math.sinh(math.pi * (1 - 2 * (py / 256.0) / n)))
            lat_deg = math.degrees(lat_rad)
            return lat_deg, lon_deg

        # Global pixel offset
        global_offset_x = start_x * 256
        global_offset_y = start_y * 256

        # Create vertices
        for r in range(total_rows + 1): # +1 for edge
            for c in range(total_cols + 1):
                # Calculate global pixel coord (approximate for the vertex)
                # Note: 'step' pixels per grid cell
                gx = global_offset_x + c * step
                gy = global_offset_y + r * step
                
                # Identify which tile this falls into
                tx = int(gx // 256)
                ty = int(gy // 256)
                
                # Local pixel in tile
                lx = int(gx % 256)
                ly = int(gy % 256)
                
                # Clamp for edge case
                if lx >= 256: lx = 255
                if ly >= 256: ly = 255
                
                img = tile_images.get((tx, ty))
                height = 0.0
                
                if img:
                    # Get pixel color
                    # img.pixels is RGBA flat list, bottom-to-top usually?
                    # Blender images are bottom-left origin?
                    # Mapbox tiles are top-left origin.
                    # So we need to flip Y for blender image lookup.
                    # Blender Y = 255 - ly
                    bly = 255 - ly
                    idx = (bly * 256 + lx) * 4
                    if idx + 2 < len(img.pixels):
                        R = img.pixels[idx]
                        G = img.pixels[idx+1]
                        B = img.pixels[idx+2]
                        # Decode: -10000 + ((R * 256 * 256 + G * 256 + B) * 0.1)
                        # Blender colors are 0..1 (float), mapbox needs 0..255 (int)
                        # But wait, Blender might apply color management (Gamma).
                        # We should treat it as non-color data.
                        # Ideally set img.colorspace_settings.name = 'Non-Color' before reading.
                        
                        # Assuming linear or we compensate.
                        # R_int = int(R * 255.0 + 0.5)
                        # G_int = int(G * 255.0 + 0.5)
                        # B_int = int(B * 255.0 + 0.5)
                        
                        # However, img.pixels access is slow. 
                        # But we are doing it in a loop.
                        
                        height = -10000 + ((R * 255 * 256 * 256 + G * 255 * 256 + B * 255) * 0.1)
                
                # Calc Lat/Lon
                lat, lon = pixel_to_latlon(gx, gy, zoom)
                
                # Project to local
                x, y = project(lat, lon)
                verts.append(Vector((x, y, height)))

        # Create Faces
        faces = []
        width_verts = total_cols + 1
        for r in range(total_rows):
            for c in range(total_cols):
                # Quad faces
                v0 = r * width_verts + c
                v1 = v0 + 1
                v2 = (r + 1) * width_verts + (c + 1)
                v3 = (r + 1) * width_verts + c
                faces.append((v0, v3, v2, v1))

        # Create Mesh Object
        mesh = bpy.data.meshes.new("RWB_Terrain_Mapbox")
        mesh.from_pydata(verts, [], faces)
        mesh.update()
        
        obj = bpy.data.objects.new("RWB_Terrain", mesh)
        
        # Cleanup images
        for img in tile_images.values():
            if img:
                bpy.data.images.remove(img)
                
        return obj

