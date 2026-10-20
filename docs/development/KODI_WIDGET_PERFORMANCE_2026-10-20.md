# AcTweeteR widget performance: Mac versus Lenovo

First live baseline: Kodi 21.3 and XStream 1.1.2.10, direct JSON-RPC Files.GetDirectory (does not measure image decoding).

| Query | Lenovo TB330FU | Mac Master | Rows |
|---|---|---|---|
| Movie recent | 3.67 / 3.70 s | 1.58 / 1.51 s | 21 |
| Movie popular | 4.22 / 4.02 s | 1.39 / 1.17 s | 14 |

Kodi window transition on Lenovo was ~0.59 s for Movies and ~0.57 s for Series. The controller focus did not reveal when artwork finished; these are not full render completion times.

## First experimental optimization

In 1.1.2.10, each movie premium widget invokes VOD-info prefetch and creates threads for every selected title, with 200 ms sleeps between 4-title batches, even for records already cached. The new 1.1.2.11 patch filters already-cached records and creates no threads or sleeps for completely warm-cache requests. Original missing-record fetch, bounded threading and throttling remain. It also avoids prefetch when movie provider metadata is disabled.

The only ZIP payload differences are addon.py, addon.xml and the modifications notice. Profile credentials, parental controls, catalog identity, play URLs, TMDb enrichment and licenses are unchanged.

Four isolated tests cover warm cache, disabled metadata, one missing, and five missing records. Live A/B testing must verify the reduction using the read-only benchmark helper.

Next investigations: Series requests, multiple independent widget refreshes, Spotlight metadata, GPU artwork decoding and Android thermals.
