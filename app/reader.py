from pathlib import Path
from zipfile import BadZipFile, ZipFile

import geopandas as gpd


def read_geofile(path: Path) -> gpd.GeoDataFrame:
    """
    Reads a geospatial file and returns a GeoDataFrame.
    Supports KML and ZIP files containing shapefiles.
    """
    extension = path.suffix.lower()

    if extension == ".kml":
        return gpd.read_file(path)
    if extension == ".zip":
        return _read_zipped_shapefile(path)
    raise ValueError("Unsupported file type. Only KML and ZIP files are allowed.")


def _read_zipped_shapefile(path: Path) -> gpd.GeoDataFrame:
    """
    Validates a zipped shapefile and reads it directly from the zip, without extracting.
    """
    try:
        with ZipFile(path) as archive:
            names = archive.namelist()
    except BadZipFile:
        raise ValueError("The uploaded file is not a valid zip archive.")

    # Find .shp files, ignoring hidden macOS metadata entries
    shp_files = [
        name for name in names
        if name.lower().endswith(".shp") and not name.startswith("__MACOSX/")
    ]
    if not shp_files:
        raise ValueError("No shapefile (.shp) found in the ZIP archive.")

    shp_name = shp_files[0]

    # A shapefile needs its .shx and .dbf parts, with the same name, to be readable
    lowercase_names = {name.lower() for name in names}
    base = shp_name[:-4].lower()                     # "data/plots.shp" -> "data/plots"
    for ext in (".shx", ".dbf"):
        if base + ext not in lowercase_names:
            raise ValueError(f"Shapefile is missing its {ext} file.")

    # Let GDAL read the .shp straight from inside the zip
    return gpd.read_file(f"zip://{path.resolve().as_posix()}!{shp_name}")