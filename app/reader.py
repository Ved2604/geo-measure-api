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
    Extracts a zipped shapefile and returns it as a GeoDataFrame.
    """
    try:
        archive = ZipFile(path)
    except BadZipFile:
        raise ValueError("The uploaded file is not a valid zip archive.")

    with archive:
        # Find .shp files, ignoring hidden macOS metadata entries
        shp_files = [
            name for name in archive.namelist()
            if name.lower().endswith(".shp") and not name.startswith("__MACOSX/")
        ]
        if not shp_files:
            raise ValueError("No shapefile (.shp) found in the ZIP archive.")

        target_folder = path.parent / "extracted"
        archive.extractall(path=target_folder)

    # Path to the extracted .shp file
    shp_path = target_folder / shp_files[0]

    # A shapefile needs its .shx and .dbf parts to be readable
    for ext in (".shx", ".dbf"):
        if not shp_path.with_suffix(ext).exists():
            raise ValueError(f"Shapefile is missing its {ext} file.")

    return gpd.read_file(shp_path)