# Data licenses and attribution

The `cf-regions` source code is Apache-2.0. The bundled geometry catalog is a
collective/derived dataset assembled from the sources below. Upstream data is
not relicensed under Apache-2.0; its original terms continue to apply.

This file is the legal and attribution reference. For the technical role of
each source and the lookup pipeline, see
[Data sources and mapping method](docs/data-sources-and-mapping.md). Maintainers
should follow [Dataset maintenance](docs/dataset-maintenance.md) when updating
vocabularies, geometries, or hierarchy data.

In the Python distribution's compound license expression,
`LicenseRef-NASA-Open-Data` refers to the NASA ESDIS reuse basis documented
below and `LicenseRef-Public-Domain` refers to the Natural Earth materials that
their publisher dedicates to the public domain.

## CF Standardized Region Lists v1–v5

- Role: canonical identifiers and the few supplied descriptions
- Versions/dates: 1 (12 December 2002), 2 (12 July 2013), 3 (11 July
  2018), 4 (18 December 2018), and 5 (12 November 2024)
- Sources: <https://cfconventions.org/Data/standardized-region-list/>
- Terms: the CF website is made available under
  [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/); the exact XML
  is retained in the package for validation and provenance.

CF does not supply the boundaries in this project. Nothing here should be
described as an official CF polygon.

## NASA GCMD Location Keywords

- Role: hierarchical location paths and connected-parent interpretation
- Version/date: 24.8, revised 16 September 2026
- Source: <https://gcmd.earthdata.nasa.gov/kms/concepts/concept_scheme/locations>
- Reuse basis: NASA ESDIS content is generally not copyrighted, and unmarked
  NASA-led data is provided under CC0 according to the
  [NASA Earthdata Data Use and Citation Guidance](https://www.earthdata.nasa.gov/engage/open-data-services-software/data-use-policy).
  NASA requests acknowledgment as the source.

Only curated hierarchy paths and version metadata are included, not the full
GCMD export. Composite-ocean and diagnostic-section connections supplement the
GCMD paths and are identified as such in the manifest limitations.

## SeaVoX Salt and Fresh Water Body Gazetteer polygons v19

- Role: 31 exact marine-area interpretations and ocean hierarchy dissolves
- Version: 19
- Publisher: Flanders Marine Institute (VLIZ), Marine Regions
- DOI: <https://doi.org/10.14284/590>
- Download: <https://www.marineregions.org/download_file.php?name=SeaVoX_sea_areas_polygons_v19.zip>
- License: [Creative Commons Attribution 4.0 International
  (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/legalcode)

Requested attribution:

> Flanders Marine Institute (2023). SeaVoX Salt and Fresh Water Body Gazetteer.
> Version 19. Available online at Marine Regions. DOI: 10.14284/590.

The package selects or dissolves features through pinned MRGIDs, creates
documented low- and high-detail simplifications for distribution, and records
the selector in each feature. Both representations preserve the source-defined
extent; in particular, no project-specific boundary is inserted between the
North Sea and Baltic Sea. Marine
Regions data is generalized and not intended for navigation or legal boundary
determination. See <https://www.marineregions.org/disclaimer.php>.

## Natural Earth

- Role: continent/region polygons, lower-48 state polygons, lakes, global land
  and ocean masks, and South China Sea
- Scale and upstream versions: 1:50m; versions 4.1.0 through 5.1.1 as recorded by
  layer in each feature
- Source: <https://www.naturalearthdata.com/>
- Terms: public domain, <https://www.naturalearthdata.com/about/terms-of-use/>

Natural Earth reflects a generalized, de-facto boundary worldview. The
`contiguous_united_states` feature is the union of the lower 48 states plus the
District of Columbia and excludes Alaska and Hawaii.

## OMIP protocol

- Role: approximate endpoints for 16 ocean transport sections
- Citation: Griffies et al. (2016), *OMIP contribution to CMIP6: experimental and
  diagnostic protocol for the physical component of the Ocean Model
  Intercomparison Project*, Geoscientific Model Development 9, 3231–3296
- DOI: <https://doi.org/10.5194/gmd-9-3231-2016>
- License: [CC BY 3.0](https://creativecommons.org/licenses/by/3.0/legalcode)

The endpoints come from Appendix J, Table J1. The paper explicitly treats them
as approximate and model-grid dependent. This project normalizes coordinate
order to longitude/latitude, maps paper labels to canonical CF names, and
encodes the endpoints as GeoJSON lines.

## CMIP6 CMOR tables

- Role: Canadian Archipelago diagnostic section and the sea-ice Fram Strait
  variant
- Source: <https://github.com/PCMDI/cmip6-cmor-tables>
- License: BSD-3-Clause

This project extracts two endpoint definitions, corrects the upstream Canadian
Archipelago spelling to the canonical CF spelling, and combines the two Fram
Strait contexts in one `MultiLineString`.

The required upstream notice follows:

> BSD 3-Clause License
>
> Copyright (c) 2017, PCMDI (Program for Climate Model Diagnosis and
> Intercomparison). All rights reserved.
>
> Redistribution and use in source and binary forms, with or without
> modification, are permitted provided that the following conditions are met:
>
> 1. Redistributions of source code must retain the above copyright notice,
> this list of conditions and the following disclaimer.
> 2. Redistributions in binary form must reproduce the above copyright notice,
> this list of conditions and the following disclaimer in the documentation
> and/or other materials provided with the distribution.
> 3. Neither the name of the copyright holder nor the names of its contributors
> may be used to endorse or promote products derived from this software without
> specific prior written permission.
>
> THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
> AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
> IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
> ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
> LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
> CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
> SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
> INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
> CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
> ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
> POSSIBILITY OF SUCH DAMAGE.

## Project-authored and derived geometry

Analytical world/hemisphere boxes are project-authored under Apache-2.0.
Composite geometries retain the applicable upstream data terms. The
Indo-Pacific mask is explicitly an interpretation of the CF description, not an
upstream authoritative boundary.

## Web-map dependencies

`cf-regions-map` loads [MapLibre GL JS 6.10.0](https://github.com/maplibre/maplibre-gl-js/tree/v6.10.0)
(BSD-3-Clause and bundled third-party notices) from unpkg and OpenStreetMap
tiles at runtime. OpenStreetMap attribution is displayed on the map; map data is
available under the [Open Database License](https://www.openstreetmap.org/copyright),
and use of the community tile service is subject to its
[tile usage policy](https://operations.osmfoundation.org/policies/tiles/).
Neither dependency is embedded in the region dataset. `cf-regions-gui` instead
draws the bundled vector representations with Qt and makes no network requests.
