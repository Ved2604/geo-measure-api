# Geospatial File Measurement API

A FastAPI service that accepts a **KML** file or a **zipped Shapefile**, extracts every feature, and calculates the **area** of polygons and the **length** of lines in metres, after reprojecting each feature to a suitable projected coordinate system.

## Setup

Requires Python 3.10+. GDAL comes bundled with the `pyogrio` package, so no separate GDAL installation is needed.

```bash
git clone https://github.com/Ved2604/geo-measure-api.git
cd geo-measure-api
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows (Command Prompt)
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate
```

Install the dependencies and start the server:

```bash
pip install -r requirements.txt
uvicorn app.main:app --reload
```

The API runs at `http://127.0.0.1:8000`, with interactive documentation at `http://127.0.0.1:8000/docs`.

Results are stored in a SQLite database file, `geo.db`, created automatically on first start. Uploaded files are saved under `storage/<file_id>/`. Delete `geo.db` and `storage/` to start from a clean state.

## API

| Method | Endpoint                             | Description                                             |
| ------ | ------------------------------------ | ------------------------------------------------------- |
| `GET`  | `/health`                            | Health check                                            |
| `POST` | `/api/files/`                        | Upload a `.kml` file or a `.zip` containing a Shapefile |
| `GET`  | `/api/files/{file_id}/`              | File information and processing status                  |
| `GET`  | `/api/files/{file_id}/measurements/` | Measurements for every feature in the file              |

### Upload a file

Send the file as `multipart/form-data` in a field named `file`.

```bash
curl -F "file=@survey.kml" http://127.0.0.1:8000/api/files/
```

```json
{
  "id": "723b99e3146844b88ed0634ab32330cb",
  "filename": "survey.kml",
  "status": "COMPLETED",
  "crs": "EPSG:4326",
  "feature_count": 3,
  "error": null
}
```

| Response                                             | When                                                                                                                                                          |
| ---------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `201` with `status: "COMPLETED"`                     | The file was read and every feature processed                                                                                                                 |
| `201` with `status: "FAILED"` and an `error` message | The file was saved but its contents could not be read, e.g. a corrupt zip, a zip without a `.shp`, a Shapefile missing its `.shx` or `.dbf`, or malformed KML |
| `400`                                                | A single Shapefile part (`.shp`, `.dbf`, ...) was uploaded on its own; the message explains how to zip the parts                                              |
| `400`                                                | Any other unsupported file type                                                                                                                               |

### Get file information

```bash
curl http://127.0.0.1:8000/api/files/723b99e3146844b88ed0634ab32330cb/
```

Returns the same fields as the upload response. Unknown ids return `404`.

### Get measurements

```bash
curl http://127.0.0.1:8000/api/files/723b99e3146844b88ed0634ab32330cb/measurements/
```

```json
{
  "file_id": "723b99e3146844b88ed0634ab32330cb",
  "feature_count": 3,
  "features": [
    {
      "index": 0,
      "geometry_type": "Polygon",
      "properties": {
        "Name": "Plot A",
        "tessellate": -1,
        "extrude": 0,
        "visibility": -1
      },
      "status": "MEASURED",
      "area_m2": 973365.153685913,
      "perimeter_m": 3946.5580291369824,
      "length_m": null,
      "projected_crs": "EPSG:32643",
      "note": null
    },
    {
      "index": 1,
      "geometry_type": "LineString",
      "properties": {
        "Name": "Road",
        "tessellate": -1,
        "extrude": 0,
        "visibility": -1
      },
      "status": "MEASURED",
      "area_m2": null,
      "perimeter_m": null,
      "length_m": 977.0660647891219,
      "projected_crs": "EPSG:32643",
      "note": null
    },
    {
      "index": 2,
      "geometry_type": "Point",
      "properties": {
        "Name": "Marker",
        "tessellate": -1,
        "extrude": 0,
        "visibility": -1
      },
      "status": "NOT_APPLICABLE",
      "area_m2": null,
      "perimeter_m": null,
      "length_m": null,
      "projected_crs": null,
      "note": "Points have no area or length."
    }
  ]
}
```

If the file's processing failed, this endpoint returns `409` with the reason. Unknown ids return `404`.

Every feature has exactly one `status`:

| Status           | Meaning                                                                                                 |
| ---------------- | ------------------------------------------------------------------------------------------------------- |
| `MEASURED`       | Polygon and MultiPolygon get `area_m2` and `perimeter_m`; LineString and MultiLineString get `length_m` |
| `NOT_APPLICABLE` | Point and MultiPoint have nothing to measure                                                            |
| `UNSUPPORTED`    | Any other geometry type, such as a GeometryCollection                                                   |
| `SKIPPED`        | The feature has no geometry, or the file's CRS is unknown                                               |

The `note` field explains every status other than `MEASURED`.

## Architecture

```
app/
├── main.py          FastAPI app: upload validation, endpoints, error handling
├── reader.py        Reads a KML or zipped Shapefile into a GeoDataFrame
├── measurement.py   Chooses a projected CRS and measures one geometry
├── processor.py     Pipeline: read file, normalise CRS, measure each feature
├── database.py      SQLAlchemy engine and per-request session
└── models.py        Database tables: files and features
```

The reading and measuring code (`reader.py`, `measurement.py`, `processor.py`) has no dependency on FastAPI. Each part can be run and tested on its own, and the API layer only handles HTTP concerns.

### File processing flow

1. **Validate the extension.** Only `.kml` and `.zip` are accepted. A lone Shapefile part gets a specific message explaining that the parts must be zipped.
2. **Save the upload** to `storage/<file_id>/uploaded.<ext>`. The file is saved under a fixed name rather than the client's filename, so a crafted name such as `../../main.py` cannot write outside the storage folder.
3. **Read the file** into a GeoDataFrame:
   - **KML** is read directly by GDAL.
   - **Zipped Shapefile**: the zip's file list is inspected without extracting anything. It must contain a `.shp` with matching `.shx` and `.dbf` files (matched case-insensitively, with hidden `__MACOSX/` entries ignored). GDAL then reads the `.shp` straight from inside the zip.
4. **Process every feature**: record its index, geometry type and properties, then measure it. Empty property values are removed and the rest converted to plain JSON types.
5. **Store the results** in SQLite: one row in `files`, one row per feature in `features`.

Problems with the file as a whole are recorded as `status: "FAILED"` with a readable message. Problems with an individual feature are recorded on that feature and never fail the whole file.

### Measurement flow

1. The whole layer is converted from its source CRS to WGS84 (EPSG:4326) longitude/latitude.
2. For each feature, altitude (Z) values are dropped, since area and length only need x and y.
3. The UTM zone covering that feature is chosen with GeoPandas' `estimate_utm_crs()`.
4. The feature is reprojected into that UTM zone, where coordinates are in metres.
5. Area and perimeter (polygons) or length (lines) are calculated, and the UTM zone used is returned as `projected_crs`.

## CRS handling

Area and length are never calculated in degrees. A degree of longitude covers about 111 km at the equator and shrinks to zero at the poles, so measurements in "square degrees" have no physical meaning.

**Choosing the projected CRS.** Each feature is measured in the UTM zone that covers its own location. UTM divides the world into 60 zones, each 6° of longitude wide, and each zone is very accurate within its own area. A plot in Bengaluru, for example, is measured in EPSG:32643 (UTM zone 43N). Choosing the zone per feature, rather than once per file, keeps measurements accurate even when one file contains features in different parts of the world.

**Source CRS:**

- **KML** is always longitude/latitude (EPSG:4326), as the KML standard requires.
- **Shapefiles** take their CRS from the `.prj` file. Any CRS works, geographic or projected, because every layer is first converted to EPSG:4326.
- A **Shapefile without a `.prj`** has no known CRS. Its features are still listed with their properties, but each is marked `SKIPPED` rather than measured. Guessing the CRS could produce confidently wrong numbers.

**Verification.** The sample `survey.kml` contains a square plot of about 0.009° × 0.009° near Bengaluru. Its measured area of 973,365 m² (about 97 hectares) matches the expected size at that latitude. The same plot saved as a Shapefile in UTM coordinates (EPSG:32643) produces the identical result, confirming the source CRS is handled correctly.

## Design decisions

| Decision                                                  | Reasoning                                                                                                                               | Alternatives considered                                                                                                                                               |
| --------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **FastAPI**                                               | Lightweight, generates interactive docs automatically, clean request handling                                                           | Django + DRF offers more built in, but is heavier than this service needs                                                                                             |
| **GeoPandas with pyogrio (GDAL)**                         | One reader for both formats, robust with real-world files, GDAL bundled in the package                                                  | Parsing KML as XML and Shapefiles with `pyshp`: fewer dependencies, but far more edge cases to handle by hand                                                         |
| **UTM zone per feature**                                  | Accurate locally, simple to explain, standard GIS practice                                                                              | One zone for the whole file is simpler but less accurate for spread-out data. Web Mercator (EPSG:3857) distorts area by about 5% in Bengaluru and over 100% in Europe |
| **Reading Shapefiles from inside the zip**                | No files written to disk, and no risk of malicious paths inside the archive; the contents are still validated first so errors are clear | Extracting the zip to a folder, which needs extra protection against path traversal                                                                                   |
| **Unreadable file returns `201` with `status: "FAILED"`** | The upload itself succeeded and has an id; the client checks one `status` field and can look the failure up later                       | Returning `422` immediately                                                                                                                                           |
| **Synchronous processing**                                | Typical survey files process in well under a second, with fewer moving parts                                                            | A background task queue (e.g. Celery or RQ with Redis), returning `202 Accepted` while processing                                                                     |
| **SQLite with SQLAlchemy**                                | Zero setup for reviewers; results survive restarts; switching to PostgreSQL only changes the connection URL                             | Keeping results in memory, which loses them on every restart                                                                                                          |
| **Skipping, not guessing, a missing CRS**                 | Wrong-but-confident numbers are worse than no numbers                                                                                   | Assuming EPSG:4326 when coordinates look like longitude/latitude                                                                                                      |

## Known limitations

- **Geometry is not yet returned** by the API, and the CRS is reported per file rather than per feature.
- **KML files with several folders**: only the first folder (layer) is read.
- **Zips with several Shapefiles**: only the first `.shp` is read.
- **Invalid polygons**, such as self-intersecting "bow-tie" shapes, are measured as they are and may give a misleading area.
- **Very wide or polar features**: a feature spanning several UTM zones, or lying beyond 84°N or 80°S, is still measured in a single UTM zone, with reduced accuracy.
- There are no automated tests yet.

## Future scope

- Return each feature's geometry as GeoJSON, through a `/features/` endpoint or an `include_geometry` option.
- Read every layer of a multi-folder KML and every Shapefile in a zip.
- Repair invalid polygons before measuring and flag them in the `note` field.
- Fall back to an equal-area projection for features too large or too far north or south for UTM.
- Automated tests with pytest.
- Pagination and file-wide totals on the measurements endpoint.
- Background processing with a task queue and Redis for very large files.
- PostgreSQL with PostGIS for spatial queries, plus Alembic migrations.
- Docker support.
- More formats: KMZ, GeoJSON, GeoPackage.

## Learnings

This was my first project working with geospatial data, so a lot of it was new to me. I started with GeoPandas and found out that a `GeoDataFrame` is basically a pandas `DataFrame` with a geometry column added on. That turned out to be really handy, because it meant I could load both KML files and zipped Shapefiles into the same structure and handle them the same way afterwards.

The thing that caught me out most was coordinate reference systems. I'd assumed I could take longitude and latitude values and calculate areas and lengths straight from them, but that doesn't work, because a degree of longitude gets shorter the closer you get to the poles. The fix was to reproject each feature into its local UTM zone, where everything is measured in metres. Once I did that, I could get proper areas for polygons like land plots and proper lengths for lines like roads.

Shapefiles taught me something too. I hadn't realised a "Shapefile" is actually several files working together, with the `.prj` file holding the CRS. I learned how to check what's inside an uploaded zip and read the Shapefile straight from it without extracting anything to disk.

On the backend, I got more comfortable using SQLAlchemy to store results. I also made sure the app returns a clear error message when someone uploads a bad file, rather than just crashing. And I learned why you shouldn't save uploaded files under whatever name the client sends.

If I did it again, I'd write tests as I went instead of checking things manually with scripts. I'd also plan out the API responses before writing any code, for example deciding up front to return each feature's geometry, rather than working that out partway through.
