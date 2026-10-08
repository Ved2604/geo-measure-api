from pathlib import Path

import numpy as np
import pandas as pd

from app.measurement import _result, measure
from app.reader import read_geofile


def process_file(path: Path) -> dict:
    """
    Reads a geospatial file and measures every feature in it.
    Returns the file's CRS, the feature count and a list of features with their measurements.
    """
    gdf = read_geofile(path)

    crs_label = gdf.crs.to_string() if gdf.crs else None

    # measure() expects longitude/latitude, so convert once for the whole table
    gdf_4326 = gdf.to_crs("EPSG:4326") if gdf.crs else None

    features = []
    for index, row in gdf.iterrows():
        geom = row.geometry

        feature_info = {
            "index": int(index),
            "geometry_type": geom.geom_type if geom is not None else None,
            "properties": _clean_properties(row.drop(gdf.geometry.name).to_dict()),
        }

        if gdf_4326 is None:
            measurement = _result("SKIPPED", note="Unknown CRS (missing .prj file), so the feature cannot be measured.")
        else:
            measurement = measure(gdf_4326.geometry.loc[index])

        features.append({**feature_info, **measurement})

    return {"crs": crs_label, "feature_count": len(features), "features": features}


def _clean_properties(properties: dict) -> dict:
    """Drops empty values and converts the rest into plain JSON-friendly Python types."""
    cleaned = {}
    for key, value in properties.items():
        if value is None or (pd.api.types.is_scalar(value) and pd.isna(value)):
            continue
        if isinstance(value, np.generic):        # numpy int/float -> Python int/float
            value = value.item()
        if isinstance(value, pd.Timestamp):      # dates -> text like "2026-10-08T00:00:00"
            value = value.isoformat()
        if value == "":
            continue
        cleaned[key] = value
    return cleaned