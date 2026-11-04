"""Static catalog data shipped with mkcv (model capabilities and prices).

``mkcv.core.models.pricing`` derives ``MODEL_PRICING`` from the data in this
package at import time, and the data modules in turn import from
``mkcv.core.models``. Importing the models package first keeps that cycle
resolvable no matter which of the two packages a caller imports first.
"""

import mkcv.core.models  # noqa: F401
