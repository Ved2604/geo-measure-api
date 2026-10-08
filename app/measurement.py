import geopandas as gpd
import shapely

AREA_TYPES = {"Polygon", "MultiPolygon"}
LENGTH_TYPES = {"LineString", "MultiLineString"}
POINT_TYPES = {"Point", "MultiPoint"}


def _result(status, area_m2=None, perimeter_m=None, length_m=None, projected_crs=None, note=None) -> dict:
    """Build a measurement result. Every result has the same keys."""
    return {
        "status": status,
        "area_m2": area_m2,
        "perimeter_m": perimeter_m,
        "length_m": length_m,
        "projected_crs": projected_crs,
        "note": note,
    }


def measure(geom) -> dict:
    """
    Measures one geometry given in EPSG:4326 (longitude/latitude).
    Polygons get area and perimeter, lines get length, both in metres.
    """
    if geom is None or geom.is_empty:
        return _result("SKIPPED", note="Feature has no geometry.")
    if geom.geom_type in POINT_TYPES:
        return _result("NOT_APPLICABLE", note="Points have no area or length.")
    if geom.geom_type not in AREA_TYPES | LENGTH_TYPES:
        return _result("UNSUPPORTED", note=f"Measurement is not supported for {geom.geom_type}.")

    # Drop altitude (Z) values: area and length only need x and y
    geom = shapely.force_2d(geom)

    # Find the UTM zone for this feature and convert it to metres
    series = gpd.GeoSeries([geom], crs="EPSG:4326")
    utm = series.estimate_utm_crs()
    projected = series.to_crs(utm).iloc[0]
    crs_label = utm.to_string()

    if geom.geom_type in AREA_TYPES:
        return _result(
            "MEASURED",
            area_m2=float(projected.area),
            perimeter_m=float(projected.length),  # for a polygon, length is its perimeter
            projected_crs=crs_label,
        )
    else:
        return _result("MEASURED", length_m=float(projected.length), projected_crs=crs_label)