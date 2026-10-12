# Related work and comparison plan

## Verified reading

| Work | Method/data described by source | Relation and limit |
|---|---|---|
| Prakash, *Near-drowning Early Prediction Technique Using Novel Equations (NEPTUNE) for Swimming Pools* (2018), [arXiv:1805.02530](https://arxiv.org/abs/1805.02530), [conference volume](https://csitcp.org/volume/818) | Statistical image processing over 1–5 second video sequences, K-means segmentation, and rule equations. The abstract reports a goal of zero false positives; that is an author claim, not a result independently reproduced here. | Temporal rules underscore why still-image detection is not event assessment. Source-video test protocol and comparability need full paper review. |
| Salehi et al., *An Automatic Video-based Drowning Detection System for Swimming Pools Using Active Contours* (2016), [journal PDF](https://www.mecs-press.org/ijigsp/ijigsp-v8-n8/IJIGSP-V8-N8-1.pdf) | HSV color-space processing and contour-based swimmer tracking are described by the paper. | Traditional video baseline candidate; extract exact dataset/protocol/metrics from the full paper before numeric comparison. |
| Woinoski et al., *Towards Automated Swimming Analytics Using Deep Neural Networks* (2020), [arXiv:2001.04433](https://arxiv.org/abs/2001.04433) | Discusses swimmer detection/tracking and the shortage of swimmer databases using competition footage. | Relevant for tracking/dataset design, not a drowning classifier. |
| Gomez Chavez et al., *CADDY Underwater Stereo-Vision Dataset for HRI in Diver Activities* (2019), [JMSE DOI 10.3390/jmse7010016](https://doi.org/10.3390/jmse7010016), [project data page](https://robotics.constructor.university/code-data/datacode-diver-pose-estimation/) | Describes underwater diver stereo imagery; the project page states 12,000 stereo pairs with IMU body-pose measurements. | Could support a separate underwater pose/tracking robustness study. Diver gear and AUV conditions differ from pools; no drowning-event labels. The paper is CC BY 4.0, but a separate data license was not confirmed and the linked dataset host timed out during this audit. |

No apples-to-apples baseline result can be reported. The supplied Roboflow image dataset has no demonstrated event timelines or independent source-video split, and its test split contains cross-split exact duplicates. A valid comparison should use the same videos, source-level partition, annotation policy, and event-level metrics (sensitivity, precision, time-to-detection, false alarms per camera-hour) and report detector metrics separately from event metrics. No novelty claim is made.

## Dataset discovery

The provided Roboflow Universe export is the only dataset selected in this repository. Candidate pools found in literature have not been treated as downloadable training data because their licensing/access and temporal labels have not been independently verified. For example, NEPTUNE is a paper describing a method, not a dataset release. The project needs a rights-cleared video set with event boundaries and source IDs before training the temporal classifier.
