from fairseq2.assets import AssetDownloadManager, get_asset_store
from fairseq2.runtime.dependency import get_dependency_resolver
from fairseq2.utils.uri import Uri
from fairseq2.data.tokenizers.hub import load_tokenizer

MODEL = "omniASR_CTC_1B_v2"
# Download through fairseq2's cache without loading multi-GB weights into RAM.
card = get_asset_store().retrieve_card(MODEL)
manager = get_dependency_resolver().resolve(AssetDownloadManager)
uri = Uri.maybe_parse(card.field("checkpoint").as_(str))
if uri is None:
    raise ValueError("Checkpoint URL is invalid")
manager.download_model(uri, MODEL)
load_tokenizer(MODEL)
