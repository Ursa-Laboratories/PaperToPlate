from pathlib import Path
import json, shutil, hashlib, re, html, zipfile

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'review-pack'
for directory in ['sources', 'evidence', 'assets', 'protocols']:
    (OUT / directory).mkdir(parents=True, exist_ok=True)
inventory = {x['filename']: x for x in json.loads((ROOT / 'inventory.json').read_text())}

def step(id, title, procedure, pages, quote, values=None, status='reported'):
    return dict(id=id, title=title, procedure=procedure, source_pages=pages,
                source_quote=quote, values=values or {}, evidence_status=status)

def issue(title, detail, pages, severity='resolve before execution'):
    return dict(title=title, detail=detail, source_pages=pages, severity=severity)

protocols = [
 dict(
  id='peroxide', short_title='Peroxide mixture quantification',
  filename='chemrxiv.15000337_v1.pdf',
  scope='The three iodide-based microplate assays for PMS, hydrogen peroxide and PDS. Begins with prepared samples and standardized peroxide stocks; electrolysis and iodometric stock standardization are outside this extracted assay module.',
  rationale='Explicit sample/reagent transfers, matched matrix blanks, replicate requirements, temperature and time-resolved readings are all in the same Methods page.',
  primary_page=5, image='peroxide-p5.png',
  summary=['96-well polystyrene plate', '250 µL per well', '350 nm at 25 °C', '0–10 s / 3 min / 8 min'],
  materials=[
   ['Sample and matching matrix', 'Prepared peroxide sample; ultrapure water or the same electrolyte as the sample for blanks.', '5'],
   ['KI stock', 'Reported as 1.2 M: 19.9 g KI dissolved in 100 mL ultrapure water. The text describes solvent volume, not an explicit final-volume make-up.', '5'],
   ['Phosphate stock', 'pH 4.0. The text labels it 0.1 M but later uses 0.5 M and gives 68 g KH₂PO₄ in 1 L water. Concentration is unresolved; retain both reported labels.', '5'],
   ['Molybdate stock', 'Reported as 35 mM: 0.124 g (NH₄)₆Mo₇O₂₄·4H₂O dissolved in 20 mL ultrapure water. Confirm whether the molarity is expressed per Mo equivalent.', '5'],
   ['Bicarbonate stock', '2 M KHCO₃. Its stock-preparation quantities are not given here.', '5'],
   ['Readout', 'Agilent PowerWave HT microplate reader; polystyrene 96-well plate; absorbance at 350 nm and 25 °C.', '5'],
  ],
  steps=[
   step('P01','Prepare indicator mix 1 (KI)', 'Combine 14 mL phosphate stock (specified here as 0.5 M, pH 4.0) with 1 mL of 1.2 M KI. The authors report 80 mM KI in mix 1. Resolve the conflicting phosphate-stock labels before preparation.', [5], '14 mL phosphate buffer stock (0.5 M, pH 4.0) with 1 mL KI stock (1.2 M)', {'transfers_ul':[14000,1000]}, 'reported_with_conflict'),
   step('P02','Prepare indicator mix 2 (KI/Mo)', 'Combine 13.83 mL phosphate stock (specified here as 0.5 M, pH 4.0), 667 µL of 1.2 M KI and 500 µL of the reported 35 mM molybdate stock. Reported mix concentrations: 53 mM KI and 1.2 mM molybdate.', [5], '667 µL KI stock (1.2 M) and 500 µL molybdate stock (35 mM)', {'transfers_ul':[13830,667,500]}, 'reported_with_conflict'),
   step('P03','Prepare indicator mix 3 (KI/KHCO₃)', 'Combine 12.5 mL of 1.2 M KI with 7.5 mL of 2 M KHCO₃. The authors report 0.75 M each of KI and KHCO₃ in mix 3.', [5], '12.5 mL KI stock (1.2 M) and 7.5 mL KHCO3 (2 M)', {'transfers_ul':[12500,7500]}),
   step('P04','Check indicator-stock background', 'Keep stocks refrigerated in the dark. The paper describes storage for several weeks and regular fresh preparation; it discarded and remade indicator stocks when blank absorbance at 350 nm exceeded 0.15. No precise shelf life or refrigerator temperature is given.', [5], 'absorbance of the blank at 350 nm was above 0.15', {'blank_absorbance_threshold':0.15}),
   step('P04b','Establish each branch’s calibration', 'Use standardized PMS for KI calibration; separate PMS and H₂O₂ standards for the combined KI/Mo calibration; and separate PMS, H₂O₂ and PDS standards for total-peroxide calibration. Reported quantification ranges are 7–250 µM, 4–250 µM and 17–500 µM respectively. Individual calibration points and dilution-transfer recipes are not specified here. Verify calibration in the actual plate geometry as the authors require.', [5,7], 'quantification range of 7 – 250 µM', {'ki_range_um':[7,250],'ki_mo_range_um':[4,250],'ki_khco3_range_um':[17,500],'standard_points_um':None}),
   step('P05','Load the PMS assay and matrix blank', 'Add 100 µL sample to each assay well, with at least two wells for the same sample. In a separate blank well, add 100 µL water or the matching electrolyte. These are separate wells, not additions to one well.', [5], '100 µL of a sample containing various peroxides were placed in a well', {'sample_ul':100,'matrix_blank_ul':100,'minimum_sample_wells':2}),
   step('P06','Start and read the PMS assay', 'Add 150 µL mix 1 to each sample and blank well. Measure absorbance at 350 nm, 25 °C immediately after addition. Results specify a 0–10 second window; the authors describe approximately 3–5 seconds between addition and their first measurement. Subtract the matrix-blank reading and use the KI-assay calibration.', [5,6,8], '150 µL of mix 1', {'indicator_ul':150,'well_total_ul':250,'wavelength_nm':350,'temperature_c':25,'measurement_window_seconds':[0,10],'reported_first_measurement_delay_seconds':[3,5]}),
   step('P07','Load and start the combined PMS + H₂O₂ assay', 'In fresh wells, add 100 µL sample or matching matrix blank, then 150 µL mix 2. Include replicate measurements as described for the PMS assay. This branch measures the combined PMS and H₂O₂ response.', [5], '150 µL of mix 2 were added to all the prepared wells', {'sample_ul':100,'indicator_ul':150,'well_total_ul':250}),
   step('P08','Read the combined PMS + H₂O₂ assay', 'Begin reading at 350 nm immediately after mix 2 addition. Record for 3 minutes at 10-second intervals at 25 °C. Use the baseline-corrected mean between 2 and 3 minutes with the KI/Mo calibration.', [5], 'for 3 minutes in 10 s intervals at 25 °C', {'duration_seconds':180,'interval_seconds':10,'mean_window_seconds':[120,180],'wavelength_nm':350,'temperature_c':25}),
   step('P09','Load and start the total-peroxide assay', 'In another set of wells, mix 50 µL sample with 200 µL mix 3. For the corresponding background, combine 50 µL matching matrix with 200 µL mix 3. Replicate determination is recommended.', [5], '50 µL of sample were mixed with 200 µL of mix 3', {'sample_ul':50,'indicator_ul':200,'well_total_ul':250}),
   step('P10','Read the total-peroxide assay', 'At 25 °C, measure absorbance at 350 nm for 8 minutes at 10-second intervals, starting immediately after indicator addition. Baseline-correct and use the mean between 5 and 8 minutes with the total-peroxide calibration.', [5], 'mean absorbance between 5 and 8 minutes', {'duration_seconds':480,'interval_seconds':10,'mean_window_seconds':[300,480],'wavelength_nm':350,'temperature_c':25}),
   step('P11','Calculate the three analyte concentrations', 'PMS comes from the KI branch. H₂O₂ = concentration from KI/Mo minus PMS from KI. PDS = total concentration from KI/KHCO₃ minus the combined concentration from KI/Mo. Apply each branch’s calibration to concentration before subtraction; raw absorbances are not interchangeable.', [5], '[H2O2] = [PMS + H2O2]KI/Mo − [PMS]KI', {'formulas':['H2O2 = C_KI_Mo - C_KI','PDS = C_KI_KHCO3 - C_KI_Mo']}),
  ],
  derived=[
   ['Final well volumes','100 + 150 = 250 µL for KI and KI/Mo; 50 + 200 = 250 µL for KI/KHCO₃.','Arithmetic from reported transfers.'],
   ['Sample dilution in the readout','2.5-fold for the first two branches and 5-fold for the third.','Arithmetic; verify the calibration concentration basis before comparing or subtracting concentrations.'],
   ['Indicator dilution in the wells','The written mix recipes and additions imply 48 mM KI in branch 1, approximately 32 mM KI / 0.72 mM molybdate in branch 2, and 0.60 M KI / KHCO₃ in branch 3.','Arithmetic from stock labels; the Results use 80 mM, 53 mM / 1.2 mM and 0.75 M labels. Resolve stock-versus-final concentration conventions before using the method.'],
  ],
  issues=[
   issue('Conflicting phosphate-stock concentration','The stock paragraph says 0.1 M, while both mix recipes specify 0.5 M. The 68 g/L recipe is also consistent with approximately 0.5 M KH₂PO₄. The extraction preserves this conflict instead of silently choosing a value.',[5]),
   issue('Stock-versus-final concentration labels','The recipe adds indicator stock to sample, diluting it. Results label conditions with the same concentrations as those indicator stocks. Clarify whether these are stock or final-well labels; do not change either recipe silently.',[5,6,8]),
   issue('Fast timing and unspecified mixing','PMS is measured within 0–10 seconds; the reported initial read was after about 3–5 seconds. Mixing method, speed and duration are absent. Dispensing/read latency must preserve the stated kinetic window.',[5,6,8]),
   issue('Calibration and stock verification need supporting detail','The paper refers to SI for titration and Table S1. Those separate supplements are not included with this selected main-article PDF. Exact calibration preparation and dilution accounting need review. The authors explicitly say calibration depends on the container/path length.',[5,6]),
   issue('Molybdate concentration basis','The salt contains seven Mo atoms. Preserve the stated mass, solvent volume and “35 mM” label; confirm the intended molarity basis rather than assuming salt molarity.',[5]),
  ],
 ),
 dict(
  id='chloride', short_title='Chloride transport in vesicles',
  filename='chemrxiv-2024-kxf0x.pdf',
  scope='The manual 96-well lucigenin chloride/nitrate antiport assay. Begins with prepared lucigenin-loaded POPC vesicles and transporter stocks. The later 384-well automated workflows are separate methods and are not merged into this extraction.',
  rationale='A numbered assay sequence specifies loading, transporter addition, pipette mixing, a salt spike and a five-minute fluorescence endpoint.',
  primary_page=4, image='chloride-p4.png',
  summary=['Manual 96-well assay', '303 µL conditional total', '369 / 503 nm fluorescence', '5 min after each salt spike'],
  materials=[
   ['Prepared POPC vesicles','Body text: 2 mM POPC; internal buffer 100 µM lucigenin, 200 mM NaNO₃ and 5 mM sodium phosphate, pH 7.2. Figure 1 instead labels internal lucigenin 1 mM. This discrepancy is unresolved.', '4'],
   ['External buffer','200 mM NaNO₃ with 5 mM sodium phosphate, pH 7.2.', '4'],
   ['Transporter stocks','A concentration series of transporter in DMSO, described as 100X stocks. The individual stock concentrations and dilution-transfer recipe are not specified in the core paragraph.', '4'],
   ['NaCl spike','200 mM NaCl with 5 mM sodium phosphate, pH 7.2.', '4'],
   ['Controls and reader','DMSO-only vesicles for 0% influx; an unspecified highly potent transporter for 100% influx. Fluorescence plate reader with autoinjector.', '4'],
  ],
  steps=[
   step('C01','Load the prepared vesicles', 'Dispense vesicle suspension into the 96-well plate. The PDF literally prints “150 L per well”; the µ prefix is missing on the rendered page, not just in text extraction. A proposed interpretation is 150 µL, but this quantity remains unresolved in the structured record.', [4], '150 L per well, 2 mM POPC', {'printed_volume_value':150,'printed_volume_unit':'L','normalized_volume_ul':None,'proposed_volume_ul':150}, 'unit_unresolved'),
   step('C02','Add transporter and mix', 'Add 3 µL of the appropriate 100X transporter stock in DMSO to each assay well. Mix using a multichannel pipette. Exact mixing volume, cycle count and speed are not stated.', [4], '3 µL of 100X stock solution', {'transporter_ul':3,'stock_multiplier_reported':100,'mix_cycles':None}),
   step('C03','Include reference conditions', 'Include vesicles treated with DMSO only as the 0% chloride-influx reference and vesicles treated with a highly potent transporter as the 100% reference. Keep DMSO concentration consistent across wells, as described in the preceding assay discussion. The reference-transporter identity and dose must be resolved.', [3,4], 'vesicles treated with DMSO only as a reference for 0% chloride influx', {'zero_reference':'DMSO-only','full_reference_identity':None}),
   step('C04','Start chloride influx', 'Use the plate-reader autoinjector to add 150 µL of the NaCl-spike solution to each well. Start each well’s endpoint timing from its own salt addition.', [4], '150 µL per well, 200 mM NaCl', {'spike_ul':150,'spike_nacl_mm':200,'spike_phosphate_mm':5,'spike_ph':7.2}),
   step('C05','Read the five-minute endpoint', 'Measure fluorescence five minutes after NaCl addition: excitation 369 nm, emission 503 nm. Assay temperature, reader gain and bandwidths are not stated in this paragraph.', [4], 'excitation = 369 nm, emission = 503 nm', {'delay_seconds':300,'excitation_nm':369,'emission_nm':503,'temperature_c':None}),
   step('C06','Convert and normalize the signal', 'Use the Stern–Volmer calibration to convert fluorescence to chloride concentration, then calibrate against the 0% and 100% influx references before fitting the final Hill plots. The paper points to supplementary Figure S28 and Equation S2 for these transformations.', [4], 'creation of a Stern-Volmer plot (Figure S28)', {'calibration_source':'Supplementary Figure S28 and Equation S2','calibration_coefficients':None}),
   step('C07','Keep batch repeats distinct from well repeats', 'The reported manual-method validation used three repeated Hill plots from three different vesicle batches. Do not convert that statement into an invented requirement for three identical wells per concentration.', [6], '3 repeated Hill plots were performed in 3 different batches of vesicles', {'reported_independent_vesicle_batches':3,'wells_per_concentration':None}),
  ],
  derived=[
   ['Conditional final volume','If the missing unit in C01 is confirmed as µL: 150 + 3 + 150 = 303 µL.','Conditional arithmetic, not a reported 300 µL total.'],
   ['Conditional DMSO fraction','3 / 303 × 100 = 0.990% v/v if the transporter stock is in neat DMSO and C01 is 150 µL.','Conditional calculation. Keep identical across the concentration series.'],
  ],
  issues=[
   issue('Printed loading-volume unit is incomplete','The visual PDF says “150 L”. The proposed 150 µL interpretation is plausible for a microplate but is explicitly not treated as a resolved source value.',[4]),
   issue('Lucigenin concentration conflicts','The procedure says 100 µM internal lucigenin; Figure 1 labels 1 mM. This tenfold difference must be reconciled from the supplementary method or authors.',[4]),
   issue('Upstream preparation and calibration are external','Vesicle manufacture, the transporter dilution series, reference transporter identity/dose, Stern–Volmer coefficients and Equation S2 are not fully specified in the selected main-PDF procedure. The separate SI is not in the 100-file ZIP.',[4]),
   issue('Plate capacity and unspecified parameters','The conditional total is 303 µL, not 300 µL. Plate working volume, mixing parameters, temperature, exact well mapping and wells per concentration require decisions; none are invented here.',[4,6]),
   issue('Vesicle age affects the signal','The paper warns that leakage can reach 20% within two hours and later discusses use within 2–3 hours. A hard validity window should be reviewed for the chosen vesicle batch.',[4,7]),
  ],
 ),
 dict(
  id='kinase', short_title='Nucleoside kinase activity',
  filename='chemrxiv-2021-k0w7q.pdf',
  scope='The standard nucleoside-kinase reaction followed by the Kinase-Glo Max residual-ATP readout, using the human deoxycytidine kinase branch as the concrete example. Enzyme production, HPLC validation and optimized conditions for other enzymes remain separate.',
  rationale='A defined 150 µL enzyme reaction feeds an explicit 10 + 80 + 10 µL luminescence assay, with controls, incubation conditions and replicate counts.',
  primary_page=11, image='kinase-p11.png',
  summary=['150 µL enzyme reaction', '100 µL luminescence well', '19 h at 37 °C + heat stop', '10 min dark; 1 s read'],
  materials=[
   ['NK reaction buffer','70 mM Tris, pH 7.6; 10 mM MgCl₂; 5 mM DTT.', '11'],
   ['ATP and nucleoside','Final reaction concentrations 0.4 mM ATP and 0.33 mM nucleoside. General stocks are described as 100, 10 or 1 mM in deionized water, without assigning the exact stock to every reaction.', '10–11'],
   ['Enzyme','Standard reaction contains 0.0002 U enzyme per 150 µL. Human deoxycytidine kinase (HsdCK/NK13) is an available branch; stock activity in U/µL is not given.', '10–11'],
   ['Detection reagent','Kinase-Glo Max reagent (Promega), used at 10 µL per readout well. Reconstitution/preparation follows an external reagent method and is not specified in this PDF.', '11'],
   ['Labware and reader','96-well PCR reaction plate; 96-well white detection plate; Synergy Mx multimode reader with 1-second luminescence integration and extended dynamic range.', '11'],
  ],
  steps=[
   step('K01','Prepare reaction mixtures', 'Prepare 150 µL reactions in NK buffer containing final 0.4 mM ATP, 0.33 mM nucleoside and 0.0002 U enzyme. The source gives final composition, not exact stock-transfer volumes or order; do not manufacture those missing pipetting instructions.', [11], 'total volume of 150 µL consisting of 0.4 mM ATP, 0.33 mM nucleoside and 0.0002 U enzyme', {'reaction_total_ul':150,'atp_mm':0.4,'nucleoside_mm':0.33,'enzyme_units':0.0002,'component_transfer_volumes_ul':None}),
   step('K02','Prepare matched reaction controls', 'Prepare a negative control without enzyme, a substrate control without ATP, and a basal-activity control without nucleoside substrate. Incubate them under the same conditions as the reactions. The exact replacement volumes for omitted stocks are not stated.', [11], 'negative control without enzyme', {'controls':['without enzyme','without ATP','without nucleoside substrate']}),
   step('K03','Incubate the enzyme reaction', 'Incubate at 37 °C for 19 hours. In the plate implementation, reactions are sealed with EASYseal film and arched auto-sealing lids preheated to 50 °C. Kinase reactions were performed in duplicate.', [11,12], 'incubated at 37°C for 19 h', {'temperature_c':37,'duration_seconds':68400,'reaction_replicates':2}),
   step('K04','Stop the reaction by heating', 'Heat to 75 °C for 10 minutes. The PCR-cycler implementation specifies lid heating at 85 °C. The paper does not give a cooling/equilibration step or temperature before adding the luminescence reagent; this remains an explicit handoff gap.', [11], '75°C for 10 min with lid heat set to 85°C', {'temperature_c':75,'duration_seconds':600,'lid_temperature_c':85,'subsequent_equilibration_c':None}),
   step('K05','Prepare standards for the ATP readout', 'Prepare ATP standards in NK buffer spanning 0–500 µM. The exact standard points are not listed in the core procedure. Standards are assayed twice; samples are assayed three times. Keep this detection replication distinct from the duplicate enzyme reactions.', [11,12], 'standards ranging from 0 to 500 µM of ATP', {'standard_range_um':[0,500],'standard_replicates':2,'sample_readout_replicates':3,'standard_points_um':None}),
   step('K06','Dilute the sample in the detection well', 'Combine 10 µL stopped reaction sample or standard with 80 µL deionized water in a white 96-well assay plate. Figure 1C explicitly places water dilution before reagent addition for standards. Applying that same order to reaction samples is an interpretation to confirm; page 11 specifies their amounts but not the water/reagent addition order.', [5,11], '10 µL phosphate donor standard was mixed with 80 µL deionized water before adding 10 µL of Kinase-Glo reagent', {'sample_or_standard_ul':10,'water_ul':80,'subtotal_ul':90,'sample_addition_order':'not explicitly reported'}, 'partly_inferred_order'),
   step('K07','Add the luminescence reagent', 'Add 10 µL Kinase-Glo reagent to each detection well. The resulting final assay volume is 100 µL. Mixing parameters are not reported.', [11], '10 µL sample/standard and 10 µL Kinase-Glo reagent', {'reagent_ul':10,'well_total_ul':100,'mix_cycles':None}),
   step('K08','Incubate and read', 'Incubate in the dark for 10 minutes, then measure luminescence for 1 second with extended dynamic range. The temperature of this 10-minute detection incubation is not stated.', [11], 'after 10 min incubation in the dark', {'dark':True,'duration_seconds':600,'integration_seconds':1,'extended_dynamic_range':True,'temperature_c':None}),
   step('K09','Apply the reported control calculation', 'As printed: consumed ATP (%) = 100 − 100 × (R + B + S)/(N + S). R is mean reaction luminescence, N is mean no-enzyme-control luminescence, S is substrate-control signal, and B is the difference between negative-control and basal-activity signals. Product formation (%) = consumed ATP (%) × 1.2, restricted to 0–100%. These are the paper’s equations, not calculations on experimental data.', [11], 'multiplying the consumed ATP with the factor 1.2', {'reported_atp_formula':'100 - 100 * (R + B + S) / (N + S)','reported_product_factor':1.2,'product_bounds_percent':[0,100]}),
  ],
  derived=[
   ['Detection volume','10 µL sample + 80 µL water + 10 µL reagent = 100 µL.','Arithmetic matches the explicit reported total.'],
   ['Detection dilution','The sample/standard is 10% of the readout volume: a tenfold dilution.','Use the same handling for standards; do not apply dilution correction twice.'],
   ['Reaction amounts','150 µL × 0.4 mM = 60 nmol ATP; 150 µL × 0.33 mM = 49.5 nmol nucleoside.','Derived amounts; exact stock transfer volumes still require stock concentrations/activity.'],
  ],
  issues=[
   issue('Reaction setup lacks component volumes','The final volume/concentrations are explicit, but per-stock transfer volumes, selected stock concentrations, enzyme stock activity and dispensing order are not. These fields remain null in JSON.',[10,11]),
   issue('Cooling and readout temperature are absent','No post-75 °C cooling/equilibration procedure is stated, and the temperature of the 10-minute dark readout incubation is unspecified.',[11]),
   issue('Calibration points and reagent preparation','The 0–500 µM ATP range is reported, but exact standard points, dilution-transfer recipes and Kinase-Glo preparation are not supplied in the core method.',[11]),
   issue('Source analysis needs expert review','The ATP-consumption equation and B definition are transcribed exactly as reported. Control arithmetic and the approximate 1.2 substrate ratio should be reviewed before interpreting assay data. The paper recommends HPLC confirmation or an enzyme-dose repeat for low conversions.',[6,11]),
  ],
 ),
]

def normalize(s):
    return re.sub(r'\s+', ' ', s.replace('μ','µ').replace('\u00ad','')).strip()

checks=[]
for protocol in protocols:
    source=inventory[protocol['filename']]
    protocol['paper_title']=source['title']
    protocol['doi']=source['doi']
    protocol['doi_url']='https://doi.org/'+source['doi']
    protocol['source_sha256']=source['sha256']
    protocol['source_page_count']=source['pages']
    protocol['review_status']='Source extraction complete; unresolved details require review before execution.'
    protocol['hardware_validation']='Not performed'
    protocol['source_pdf']='sources/'+protocol['filename']
    protocol['json_path']='protocols/'+protocol['id']+'.json'
    shutil.copy2(ROOT/'sources'/protocol['filename'],OUT/protocol['source_pdf'])
    source_pages=json.loads((ROOT/'text'/(protocol['filename'][:-4]+'.json')).read_text())
    by_page={p['pdf_page']:p['text'] for p in source_pages}
    for s in protocol['steps']:
        assert all(1<=page<=source['pages'] for page in s['source_pages'])
        found=normalize(s['source_quote']) in normalize(' '.join(by_page[p] for p in s['source_pages']))
        checks.append({'step':s['id'],'quote_found':found,'source_pages':s['source_pages']})
    (OUT/protocol['json_path']).write_text(json.dumps(protocol,ensure_ascii=False,indent=2))
for p in ROOT.joinpath('evidence').glob('*.png'):
    if p.name.startswith(('peroxide-','chloride-','kinase-')):shutil.copy2(p,OUT/'evidence'/p.name)
font=ROOT.parents[1] / 'frontend/public/assets/dm-sans.ttf'
shutil.copy2(font,OUT/'assets/dm-sans.ttf')
shutil.copy2(font.with_name('DM-Sans-LICENSE.txt'),OUT/'assets/DM-Sans-LICENSE.txt')
data={
 'schema_version':1,'created_date':'2026-10-22',
 'collection':'User-downloaded ChemRxiv Workflow Catalog ZIP, 100 PDFs',
 'input_zip':'local-only: ChemRxiv Workflow Catalog ZIP (100 PDFs)',
 'screening':'All 100 titles/first pages indexed. Candidate method sections inspected. These three replace the earlier Bradford, DPPH and beer selections.',
 'method':'Direct PDF text review plus visual inspection of the key Methods pages. Page references count from the first PDF page, including the ChemRxiv cover. No external protocol was substituted.',
 'execution_status':'Review extracts only. No executable CubOS protocol generated or physical experiment performed.',
 'protocols':protocols,
}
(OUT/'protocols.json').write_text(json.dumps(data,ensure_ascii=False,indent=2))
(OUT/'verification.json').write_text(json.dumps({'source_count':3,'indexed_collection_count':100,'checks':checks,'source_hashes_verified':all(hashlib.sha256((OUT/p['source_pdf']).read_bytes()).hexdigest()==p['source_sha256'] for p in protocols)},indent=2))
print(json.dumps({'steps':len(checks),'quote_matches':sum(c['quote_found'] for c in checks),'unmatched':[c for c in checks if not c['quote_found']]},indent=2))

E=lambda s:html.escape(str(s))
def refs(p,pages):
    return ' · '.join('<a href="'+E(p['source_pdf'])+'#page='+str(n)+'" target="_blank" rel="noopener">PDF p. '+str(n)+'</a>' for n in pages)
sections=[]
for ix,p in enumerate(protocols,1):
    material_rows=''.join('<tr><th>'+E(x[0])+'</th><td>'+E(x[1])+'</td><td>'+E(x[2])+'</td></tr>' for x in p['materials'])
    steps=''.join('<article class="step"><div class="stepnum">'+E(s['id'])+'</div><div><h4>'+E(s['title'])+'</h4><p>'+E(s['procedure'])+'</p><div class="refs">'+refs(p,s['source_pages'])+'</div><details><summary>Check source wording</summary><blockquote>'+E(s['source_quote'])+'</blockquote></details></div></article>' for s in p['steps'])
    gaps=''.join('<li><h4>'+E(x['title'])+'</h4><p>'+E(x['detail'])+'</p><div class="refs">'+refs(p,x['source_pages'])+'</div></li>' for x in p['issues'])
    deriv=''.join('<tr><th>'+E(x[0])+'</th><td>'+E(x[1])+'<br><small>'+E(x[2])+'</small></td></tr>' for x in p['derived'])
    sections.append(f'''<section class="paper" id="{p['id']}" aria-labelledby="title-{p['id']}">
    <div class="eyebrow">EXTRACTION {ix:02d} / 03</div><h2 id="title-{p['id']}">{E(p['short_title'])}</h2>
    <p class="paper-title">{E(p['paper_title'])}</p><div class="links"><a href="{E(p['source_pdf'])}#page={p['primary_page']}" target="_blank" rel="noopener">Open original PDF ↗</a><a href="{E(p['json_path'])}" download>Structured JSON ↓</a><a href="{E(p['doi_url'])}" target="_blank" rel="noopener">Publication ↗</a></div>
    <div class="facts">{''.join('<span>'+E(x)+'</span>' for x in p['summary'])}</div>
    <div class="scope"><strong>Extracted scope</strong><p>{E(p['scope'])}</p><p><small>Why selected: {E(p['rationale'])}</small></p></div>
    <div class="review-grid"><div class="procedure"><h3>Materials and starting conditions</h3><div class="table-wrap"><table><thead><tr><th>Input</th><th>As reported / unresolved</th><th>PDF p.</th></tr></thead><tbody>{material_rows}</tbody></table></div><h3>Ordered procedure</h3>{steps}<h3>Arithmetic, separately labeled</h3><div class="table-wrap"><table><tbody>{deriv}</tbody></table></div><h3>Details needing review <span class="count">{len(p['issues'])}</span></h3><ul class="issues">{gaps}</ul></div>
    <aside class="source"><div class="source-heading"><strong>Source evidence</strong><span>PDF page {p['primary_page']}</span></div><a href="evidence/{p['image']}" target="_blank" rel="noopener"><img src="evidence/{p['image']}" alt="Original Methods page for {E(p['short_title'])}" loading="lazy"></a><p>Click the page to enlarge. Page links in each step open the original PDF.</p><details><summary>Provenance</summary><p>{E(p['filename'])}<br>{p['source_page_count']} PDF pages</p><code>{p['source_sha256']}</code><p>SHA-256 matches the PDF extracted from your downloaded ZIP.</p></details></aside></div></section>''')
nav=''.join('<a href="#'+p['id']+'"><span>0'+str(i)+'</span>'+E(p['short_title'])+'</a>' for i,p in enumerate(protocols,1))
page='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Three new assays — protocol extraction review</title><style>
@font-face{font-family:DM;src:url('assets/dm-sans.ttf') format('truetype');font-display:swap}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:85px}body{margin:0;background:#F6F4ED;color:#172137;font:16px/1.65 DM,Arial,sans-serif}a{color:#233C78;text-underline-offset:4px}a:hover{color:#0c2150}header{border-bottom:1px solid #cfd3d7;padding:21px 5vw;display:flex;justify-content:space-between;gap:20px;align-items:center}.brand{font-weight:700;letter-spacing:.12em;font-size:12px}header small{color:#576178}.wrap{max-width:1560px;margin:auto;padding:55px 5vw 80px}h1{font-size:clamp(36px,4.4vw,62px);line-height:1.08;letter-spacing:-.045em;font-weight:500;margin:18px 0}h2{font-size:38px;line-height:1.15;font-weight:500;letter-spacing:-.035em;margin:12px 0}h3{font-size:21px;font-weight:600;letter-spacing:-.02em;margin:34px 0 14px}h4{font-size:17px;margin:0 0 8px;font-weight:650}p{margin:8px 0 14px}.intro{max-width:850px;font-size:19px;color:#4d586d}.eyebrow{color:#233C78;font-size:11px;letter-spacing:.16em;font-weight:700}.topnote{border-left:3px solid #233C78;padding:8px 20px;max-width:1000px;margin:27px 0;color:#3e4b61;background:#eef0ef}.topnote strong{color:#172137}nav{display:flex;flex-wrap:wrap;border-top:1px solid #cbd0d8;border-bottom:1px solid #cbd0d8;margin:32px 0 0;padding:17px 0;gap:15px 30px}nav a{text-decoration:none;font-weight:600;font-size:14px}nav span{color:#6e7f9a;margin-right:8px}.paper{padding-top:52px;margin-bottom:65px}.paper-title{font-size:17px;color:#59647a;max-width:1000px}.links{display:flex;flex-wrap:wrap;gap:25px;font-size:13px;margin:18px 0 26px}.facts{display:grid;grid-template-columns:repeat(4,1fr);border-top:1px solid #b7c4d6;border-bottom:1px solid #b7c4d6;background:#D7E1F2}.facts span{padding:16px 18px;font-size:14px;font-weight:600;border-right:1px solid #bcc9dd}.facts span:last-child{border:0}.scope{max-width:1050px;margin:24px 0 12px}.scope strong{font-size:12px;text-transform:uppercase;letter-spacing:.1em}.scope p{font-size:15px}.review-grid{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(330px,.75fr);gap:42px;align-items:start}.procedure{min-width:0}.source{position:sticky;top:25px;margin-top:40px;background:#fff;border:1px solid #d4d9df;padding:13px}.source img{width:100%;display:block;border:1px solid #e2e5ea}.source-heading{display:flex;justify-content:space-between;padding:6px 4px 14px;font-size:13px}.source-heading span{color:#6a7487}.source p{font-size:12px;line-height:1.6;margin:12px 5px;color:#657084}.table-wrap{overflow:auto}table{width:100%;border-collapse:collapse;font-size:13px}th,td{text-align:left;vertical-align:top;padding:13px 11px;border-bottom:1px solid #d7dbe0}th{font-weight:600;min-width:108px}thead th{font-size:11px;text-transform:uppercase;letter-spacing:.06em;background:#eaedf0;color:#586277}small{font-size:12px;color:#657084}.step{border-top:1px solid #cfd5dc;padding:22px 0;display:grid;grid-template-columns:42px 1fr;gap:14px}.stepnum{font:12px/1.8 monospace;color:#52688a;margin-top:2px}.step p{font-size:15px;line-height:1.7}.refs{font-size:12px}.refs a{color:#526585}details{margin-top:9px;font-size:12px}summary{cursor:pointer;color:#526585}blockquote{margin:12px 0;background:#e9edf1;border-left:2px solid #9babc4;padding:12px 16px;color:#3e4d65;line-height:1.6}code{font-size:10px;overflow-wrap:anywhere}.issues{padding:0;list-style:none;border-top:2px solid #bb9065}.issues li{padding:19px 16px;border-bottom:1px solid #d6c9b9;background:#f1ebe2}.issues p{font-size:14px}.count{font-size:12px;color:#776247;margin-left:8px}.footer{border-top:1px solid #bfc8d4;padding-top:24px;color:#657084;font-size:12px}.review-method{max-width:1000px;font-size:14px;margin-top:45px}.review-method p{margin-bottom:10px}@media(max-width:950px){.review-grid{grid-template-columns:1fr}.source{position:static;max-width:650px}.facts{grid-template-columns:repeat(2,1fr)}h2{font-size:32px}.wrap{padding:35px 5vw}.source{margin-top:0}}@media(max-width:550px){.facts{grid-template-columns:1fr}.facts span{border-right:0;border-bottom:1px solid #bcc9dd}.step{grid-template-columns:32px 1fr;gap:7px}header small{display:none}h1{font-size:40px}}@media(prefers-reduced-motion:reduce){html{scroll-behavior:auto}}@media print{body{background:white;font-size:10pt}header,nav,.links,details{display:none}.wrap{padding:0}.paper{break-before:page}.review-grid{display:block}.source{display:none}.step{break-inside:avoid}h1{font-size:30pt}h2{font-size:24pt}.facts{background:#eee}.issues li{break-inside:avoid}.topnote{background:transparent}}
</style></head><body><header><div class="brand">PAPER TO PLATE / SOURCE REVIEW</div><small>22 October 2026 · Local review copy</small></header><main class="wrap"><div class="eyebrow">100 DOWNLOADED PAPERS → THREE NEW EXTRACTIONS</div><h1>Three assays.<br>Every step traceable.</h1><p class="intro">Peroxide quantification, chloride transport and nucleoside kinase activity. Original quantities and conditions are retained, with calculations and unresolved source details identified separately.</p><div class="topnote"><strong>For your review.</strong> These are extracted assay procedures. Missing values remain missing. No CubOS execution file or hardware validation is claimed. Page references include each PDF’s cover page.</div>'''+nav+''.join(sections)+'''<section class="review-method"><h3>How this extraction was checked</h3><p>All 100 PDFs were inventoried and their titles/first pages screened. Candidate Methods sections were then inspected. The three selected papers are different from the earlier Bradford, DPPH and beer selection. Each numbered step includes a PDF page and a short source excerpt; the key Methods pages were also visually inspected.</p><p>The selected source PDFs are copied byte-for-byte from the downloaded ZIP. Their hashes and the structured extraction are included. Separate supporting-information files were not present for these three papers. This review does not substitute outside recipes or silently infer missing stock volumes, temperature settings or units.</p><p><a href="protocols.json" download>All three structured extractions</a> · <a href="verification.json">Extraction verification record</a></p></section><div class="footer">Research extraction · Scientific review and hardware adaptation remain separate. The original 100-paper archive is preserved.</div></main></body></html>'''
(OUT/'index.html').write_text(page)
(OUT/'READ-ME.txt').write_text('Open index.html for the review. It includes three new assay extractions, clickable PDF page references, visual source evidence, structured JSON and unresolved questions. Page numbers include cover pages. Original PDF hashes match the downloaded ZIP. No hardware protocols were executed or generated. The three papers are peroxide-mixture quantification, chloride transport in vesicles and nucleoside-kinase activity.\n')
archive=ROOT/'three-new-assay-protocols.zip'
with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as z:
    for p in sorted(OUT.rglob('*')):
        if p.is_file():z.write(p,arcname='three-new-assay-protocols/'+str(p.relative_to(OUT)))
with zipfile.ZipFile(archive) as z:assert z.testzip() is None
print('REPORT',OUT/'index.html')
print('ZIP',archive,archive.stat().st_size)
