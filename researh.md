# Research: AI-Powered Crop Disease and Pest Detection from Phone Photos

Last updated: 10 November 2026

Note on sources: most facts below came from web search summaries, and only the dataset, GitHub and CropNet tutorial pages were read directly. Open a link and confirm the claim on that page before citing it in formal work.

## 1. The brief

From Dr. Margaret Nagwovuma's project sheet:

- A computer-vision model, using transfer learning on common Ugandan crops, identifies disease and suggests local remedies or the nearest agro-dealer.
- It works offline.
- A farmer should be guided to the location of pesticides (the geo component).
- Business angle: freemium for farmers, paid API or white-label for agribusinesses and extension services.

## 2. Main findings

1. **Openly licensed Ugandan data exists.** Makerere AI Lab and NaCRRI collected cassava and maize images on phones in farmer gardens. DatasetNinja lists both as CC0 1.0, which would allow commercial use. Section 4 explains what to confirm first.
2. **The best-known cassava data is not usable commercially.** The rules of the Kaggle cassava competition limit the data to non-commercial use, including academic research and education. It is fine for a course prototype but not for the paid API or white-label product.
3. **Neither starting link is ready to ship.** The GitHub repo states no licence, and no licence for CropNet could be confirmed. Both are useful as accuracy baselines only.
4. **"Guide the farmer to pesticides" does not fit every diagnosis.** Sources on cassava mosaic and brown streak describe prevention and clean planting material, not a curative product. The geo feature should send the farmer to the right place for each problem: an agro-dealer for maize pests, a clean-cutting source for cassava viruses.
5. **Lab accuracy will not carry over to the field.** One PlantVillage-trained model scored 99.61% internally and 66.80% on field images. The model must be trained and tested on real garden photos.
6. **Assessing more leaves helps a lot.** PlantVillage Nuru went from about 65% accuracy to 74-88% when six leaves per plant were assessed. The app should ask for several leaves.
7. **The market is real, but farmers may not all have smartphones.** Smartphones were about a third of devices in Uganda in 2025. Extension workers are stretched at an estimated 1 per 1,800 farmers. Village agents and extension staff are likely the first users.
8. **Competitors already exist.** Nuru and Plantix are the strongest, and Nuru works offline. The gap to test is verified local dealer guidance built on Ugandan data.
9. **No public agro-dealer list was found.** The dealer data will have to be collected by hand and with UNADA and MAAIF.

## 3. Which crops to start with

The 2019 Annual Agricultural Survey ([UBOS](https://www.ubos.org/wp-content/uploads/2022/04/Uganda_UBOS_StatRelease_AAS2019-Final.pdf)) is the most recent crop data found, so current planting may differ.

| Crop | Share of agricultural households (2019) | Open data found |
|---|---|---|
| Maize | 69% in season 1, 48% in season 2 | Strong, including fall armyworm |
| Banana (food) | 47% | None assessed |
| Cassava | Almost half, with banana | Strong |
| Beans | Major crop, exact share not captured | Small (1,296 images) |
| Robusta coffee | 21% | None assessed |
| Arabica coffee | 7% | None assessed |

**Recommendation: start with cassava and maize in one district.** Together they cover widely grown crops, disease and a pest. Add beans next. Banana and coffee need a separate data search.

## 4. Datasets

| Dataset | Images | Classes | Collected | Licence as listed |
|---|---|---|---|---|
| [Makerere cassava](https://datasetninja.com/makerere-university-cassava) (DOI 10.7910/DVN/T4RB0B) | 9,103 | Mosaic 4,987, brown streak 2,997, healthy 1,119 | Phones, farmer gardens, four regions of Uganda | CC0 1.0 |
| [Makerere maize](https://datasetninja.com/makerere-university-maize) (DOI 10.7910/DVN/LPGHKK) | 15,821 | Leaf blight 5,279, streak virus 5,216, healthy 5,326 | Phones, farmer gardens, four regions of Uganda | CC0 1.0 |
| [KaraAgro AI maize](https://datasetninja.com/kara-agro-ai-maize) (DOI 10.7910/DVN/CXUMDS) | 16,552 | Fall armyworm damage, larva, egg, frass; streak disease; healthy | Location not stated; survey context cites Ghana and Zambia | CC0 1.0 |
| [iBean](https://github.com/AI-Lab-Makerere/ibean) | 1,296 | Healthy, angular leaf spot, bean rust | Smartphones, districts in Uganda, labelled with NaCRRI | MIT |
| [Kaggle cassava competition](https://huggingface.co/datasets/pufanyi/cassava-leaf-disease-classification) | 21,367 (per the GitHub repo below) | Blight, brown streak, green mottle, mosaic, healthy | Survey in Uganda | Non-commercial only (rules as quoted on the mirror) |

Points to confirm:

- **CC0 status.** These licences were read on DatasetNinja, a third-party catalogue. Its pages also name the University of Ghana as publisher while crediting Makerere and NaCRRI. Check the licence field on each Harvard Dataverse record before any commercial use.
- **Fall armyworm in Uganda.** KaraAgro images may not be Ugandan, so test the pest model on Ugandan photos.
- **Missing cassava classes.** The Makerere cassava set has no bacterial blight or green mite class. The app must handle those as "not sure" rather than force a wrong label.

## 5. Starting links and model options

**[rpnugroho/cassava-disease-tflite](https://github.com/rpnugroho/cassava-disease-tflite)**

- Five cassava classes, EfficientNet-Lite3, exported to TFLite with an Android app.
- Reports 88% on hold-out data.
- Trained on the Kaggle competition data, and states no licence. Do not reuse its code or model in the product without the author's permission.

**[Google CropNet cassava classifier](https://www.tensorflow.org/hub/tutorials/cropnet_cassava)**

- Six classes, including "unknown", with 224 x 224 RGB input.
- The notebook prints 0.88 accuracy on 1,000 test examples, which is a demo result and not a benchmark.
- A [recent paper](https://sol.sbc.org.br/index.php/eniac/article/download/38824/38597) describes it as built on MobileNetV3.
- The licence could not be confirmed, because the [Kaggle model page](https://www.kaggle.com/models/google/cropnet) did not load. Its [on-device tutorial](https://www.tensorflow.org/hub/tutorials/cropnet_on_device) shows fine-tuning and TFLite export, but no ready-made TFLite file for this classifier was confirmed.

**Label warning.** The repo and Kaggle data use "CGM" for cassava green mottle, while CropNet uses "cgm" for green mite. These are different problems, so confirm the meaning with NaCRRI before attaching advice to that label.

**Recommended approach**

- Train a new model on the CC0 Ugandan data, and use the two models above only for comparison.
- Use [MediaPipe Model Maker](https://developers.google.com/edge/mediapipe/solutions/vision/image_classifier/customize), which supports EfficientNet-Lite0, Lite2, Lite4 and MobileNet-V2 and exports TFLite for Android.
- Avoid the older tflite-model-maker. Google calls MediaPipe its [next generation](https://discuss.ai.google.dev/t/future-of-tflite-model-maker-and-mediapipe-model-maker/31527), and a user in that thread reports it fails to install on Python 3.10 to 3.13. No official end-of-life notice was found.

## 6. Accuracy in real use

- Models trained on lab images drop sharply on field images: to [just above 31%](https://arxiv.org/abs/2603.13354) in a classic result, and from 99.61% to [66.80%](https://reference-global.com/article/10.2478/jee-2026-0043) in a recent test. The second figure was reached through a search summary, so confirm it against the paper.
- [PlantVillage Nuru](https://www.frontiersin.org/articles/10.3389/fpls.2020.590889/full), on cassava viral diseases: about 65% for the app, 40-58% for extension agents, 18-31% for farmers. Assessing six leaves per plant raised app accuracy to 74-88%. These figures come from published summaries of the study.
- The model needs a way to say "not sure". Thresholds trade [false alarms against missed disease](https://frontiersin.org/articles/10.3389/fpls.2022.891785/pdf), and [threshold choice strongly affects results](https://www.themoonlight.io/es/review/open-set-plankton-recognition). No study was found that covers phone apps rejecting non-plant photos.

Proposed design, which is our own suggestion rather than a sourced result:

- Capture several leaves per plant and combine the results.
- Add a "not a leaf or unknown" class with non-crop images.
- Set the confidence threshold on Ugandan validation photos, and calibrate scores first.
- When unsure, ask for a new photo or refer the farmer to an extension officer.
- Split test data by region, so results show how the model handles places it has not seen.

## 7. What the app should advise

All advice needs review by a NaCRRI or MAAIF agronomist before release.

| Problem | Advice found | Where to send the farmer |
|---|---|---|
| Cassava mosaic and brown streak | [Resistant varieties](https://pmc.ncbi.nlm.nih.gov/articles/PMC4950135), clean planting material, removing infected plants, managing whitefly. No curative product was found. | Clean-cutting source |
| Cassava bacterial blight | [Clean cuttings](https://kolibri.teacherinabox.org.au/modules/en-infonet/export/default$ct$114$crops.html) from the woody lower stem, check for browning, disinfect tools, intercrop | Clean-cutting source |
| Cassava green mite | [Clean cuttings, tolerant varieties, avoid pesticides](https://plantwiseplusknowledgebank.org/doi/10.1079/pwkb.species.34767) that kill natural enemies. The predatory mite *T. aripo* is the main biological control. | Extension officer |
| Fall armyworm on maize | [Hand-picking, weeding](https://mdpi.com/2071-1050/16/8/3118), and integrated control. Emamectin benzoate [reduced incidence by 90%](https://ir.busitema.ac.ug/handle/20.500.12283/4034) in one Ugandan trial. | Certified agro-dealer |
| Maize leaf blight and streak virus, bean diseases | Not researched yet | To be decided |

Safety and quality notes:

- **Do not publish a dose from the trial above.** It is one dissertation, not official guidance. No official MAAIF fall armyworm product list was found.
- [Farmer surveys](https://preventionweb.net/news/most-smallholder-farmers-surveyed-uganda-believe-they-can-reduce-damage-caused-fall-armyworm) in Kamuli and Namutumba found commonly used insecticides, including emamectin benzoate and lambda-cyhalothrin, considered high risk to health and the environment. Show protective guidance with every chemical suggestion.
- Only list products on MAAIF's [National Agrochemicals Register](https://publicisteastafrica.com/?p=9632). That link is a report mentioning the register, so locate the register itself.
- Variety advice ages quickly. [NaCRRI's own dossier](https://cassavabase.org/ftp/documents/variety_releases/2021_Cassava_Variety_Release_Dossier_Draft_NaCRRI.pdf) says NASE 14 and NAROCASS 1 have become less productive because of brown streak.
- Recycled cuttings of [TME 204 and similar varieties](https://nru.uncst.go.ug/items/157faa59-80fd-42a5-9813-bc8898513509) are key virus reservoirs. Advice should favour recently sourced, certified or tissue-culture material.

## 8. The geo component

**Agro-dealer data found**

- [UNADA](https://issuu.com/agribusiness/docs/agribusiness_directory_2013/17) is the national association, with 1,300 members, 93 branches and 10 regions as of 2013.
- MAAIF reported [more than 500 dealers certified](https://www.agriculture.go.ug/2021/07/06/maaif-develops-electronic-system-to-monitor-agrochemicals) since 2018.
- [About 46% of dealers](https://eprcug.org/eprc-in-the-news/substandard-agricultural-inputs-are-holding-back-farmers/) were reported as not registered with MAAIF, in a survey with no date given.
- No current public registry or map was found.

**Clean cassava planting material**

- [NaCRRI](https://core.ac.uk/download/479654908.pdf) supplies virus-clean stock to seed multipliers.
- The National Seed Certification Service in MAAIF oversees Quality Declared Seed. No current multiplier list was found.

**Proposed design** (our suggestion)

- Map 20-30 dealers and seed sources by hand in the pilot district, and ask UNADA, MAAIF and NaCRRI for lists.
- Store name, type, GPS, phone number, certification status and date last checked.
- Ship the list inside the app, and rank by straight-line distance from the phone's GPS, so it works offline. Offline map tiles can come later.
- Show a certified badge, because substandard inputs are a known problem.
- Tell farmers to phone before travelling, since live stock levels will not be known.

## 9. Competitors

| Product | Crops or focus | Offline | Notes |
|---|---|---|---|
| [PlantVillage Nuru](https://bigdata.cgiar.org/divi_overlay/plantvillage-nuru/) | Cassava, fall armyworm, potato | Yes | Backed by Penn State and partners, closest competitor |
| [Plantix](https://monitor.co.ug/uganda/magazines/farming/plantix-the-agronomist-mobile-app-changing-farmers-fortunes-4354932) | Many crops | [Partial](https://www.corteva.com/news/corteva-and-plantix-introduce-free-pest-disease-and-weed-identification-app.html), sources differ | 18-19 languages, including Swahili. Owned by Helm AG. |
| [Tumaini](https://alliancebioversityciat.org/2025-annual-report/artificial-intelligence-agriculture) | Banana, beans | Not confirmed | Alliance of Bioversity and CIAT |
| [PeDD](https://publicisteastafrica.com/?p=10699) | Pests and disease, Uganda | Not confirmed | Press claims it is the only such app in Uganda, which other products contradict |
| [Busitema University app](https://bdears.busitema.ac.ug/items/93ddf0e1-08a4-4210-b3b9-1f828a186ca0/full) | Crop disease, tested in Tororo | Yes | Academic project |
| [Banana Assist](https://dissertations.mak.ac.ug/handle/20.500.12281/21668) | Banana | Not confirmed | Makerere student project |

Plantwise, Prise and Agrio are [also named](https://www.harvestmoney.co.ug/?p=29947) as tools available in Uganda. EzyAgric and mCrops could not be confirmed either way.

**Possible difference for this product:** Uganda-trained models, certified local dealer and clean-seed guidance offline, and advice reviewed by Ugandan agronomists. Luganda or other local-language support could add to this, but no Ugandan language support was checked for competitors. All of this still needs testing with farmers.

## 10. Market and users

- **Devices:** [17.6 million smartphones](https://nilepost.co.ug/news/290349/ugandas-digital-surge-44-million-mobile-subscriptions-power-economic-shift) in June 2025. [Late 2025 figures](https://www.ugandaonline.net/news/2026-03-23--uganda-s-heavy-smartphone-taxes-trap-millions-on-feature-phones--677a214c4bfd) show about 20 million smartphones against 32.2 million feature phones. Figures vary by source.
- **Rural ownership:** no rural or farmer-specific figure was found, and this is a significant gap.
- **Extension capacity:** an [estimated 1 worker per 1,800 farmers](https://allafrica.com/stories/202512190274.html), against the 1:500 benchmark cited by MAAIF. The figure may be an older estimate that keeps being repeated. About [3,800 of a targeted 5,000](https://mediacentre.go.ug/node/96) workers were recruited.

**Implication:** one smartphone can serve many farmers. Extension workers, village agents and lead farmers are the most realistic first users, as well as a route to paying organisations.

## 11. Business model

Proposed model, to be tested:

- **Free for farmers:** diagnosis, advice and dealer guidance. No farmer willingness-to-pay data was found.
- **Paid:** white-label apps and API access for agribusinesses, NGOs and extension programmes.
- **Possible later:** anonymised, consent-based outbreak maps for government and NGOs.

**Lesson from Plantix:** it [earns a margin from retailers](https://yourstory.com/2020/04/startup-plantix-farmers-retail-inputs-crop-health) and works with agrochemical companies, and [critics say](https://www.stork.ai/en/plantix) this can influence treatment choices. Dealers should not be able to pay for a higher ranking. Trust is the product.

No pricing benchmarks were found for agricultural APIs or white-label deals in Uganda. Interviews with two or three likely buyers should come before setting prices.

## 12. Law and compliance

This is background research, not legal advice.

- **Pesticides:** MAAIF regulates pesticides under the [Agricultural Chemicals (Control) Act 2006](https://publicisteastafrica.com/?p=9632). No provision specific to app-based recommendations was found. Ask MAAIF before recommending named products.
- **Data protection:** the [Data Protection and Privacy Act](https://www.dlapiperdataprotection.com/?c=UG&t=law) and 2021 Regulations are overseen by the Personal Data Protection Office.
- **Location data:** a [legal summary](https://www.dataguidance.com/notes/uganda-data-protection-overview) says GPS data counts as geolocation data, and that an impact assessment is required before collecting or processing it. Confirm how this applies if GPS stays on the phone.
- **Design choice:** keep GPS and photos on the device by default, and ask for consent before any upload.

## 13. Still unknown

- Licence confirmation on Harvard Dataverse for the three CC0 datasets.
- CropNet's licence.
- Smartphone ownership among rural farmers.
- Official MAAIF product guidance for fall armyworm, and whether the agrochemical register is public.
- A current list of agro-dealers and cassava seed multipliers.
- Advice for maize leaf blight, maize streak virus and bean diseases.
- Banana and coffee image datasets.
- Pricing and willingness to pay.
- On-device model size and speed on low-cost Android phones.

## 14. Next steps

1. Confirm dataset licences on Harvard Dataverse.
2. Contact NaCRRI and Makerere AI Lab about data, advice review and a possible partnership.
3. Contact UNADA and MAAIF for dealer lists and pesticide guidance.
4. Choose the pilot district, and interview farmers, dealers and extension staff.
5. Interview two or three likely paying organisations.
6. Train a first cassava model, and compare it with the two baselines on field images.

## Original links

- https://github.com/rpnugroho/cassava-disease-tflite
- https://www.kaggle.com/models/google/cropnet?utm_source=chatgpt.com
