"""Generate refined wing_responses.json (v3) with pure earthquake focus and corrected Tech E&M."""
import json, os

os.makedirs("data/templates", exist_ok=True)

data = {"wings": {}}

# Defined wings
wings_meta = [
    ("tech_early_warning", "Tech Early Warning", "📡"),
    ("ops_wing", "Ops Wing", "🎯"),
    ("logistics", "Logistics", "🚚"),
    ("drr", "Disaster Risk Reduction (DRR)", "🛡️"),
    ("plans", "Plans Wing", "🗺️"),
    ("pcc", "Provincial Coordination Cell (PCC)", "🏛️"),
    ("tech_e_m", "Tech E & M", "⚙️"),
    ("military_media", "Regional Military and Media Wing", "📢"),
    ("nidm", "National Institute of Disaster Management (NIDM)", "🎓"),
    ("infra_audit", "Infra Audit and Project Development Wing", "🏗️"),
]

P = ["d_day", "d_day", "d1_to_d5", "d5_to_d10", "d10_to_d20", "d20_to_d50"] # Mapping

def w(wid, name, icon, phases_data):
    data["wings"][wid] = {"name": name, "icon": icon, "phases": phases_data}

# 1. Tech Early Warning - Focus: Seismic Monitoring
w("tech_early_warning", "Tech Early Warning", "📡", {
    "d_day": {
        "greeting": "Tech Early Warning Wing activated. M7.4 seismic event confirmed in Batagram. Analyzing initial shakemaps.",
        "actions": ["Generate initial Shakemaps", "Broadcast seismic alerts to NEOC", "Coordinate earthquake parameters with PMD", "Activate local siren systems"],
        "responses": {
            "status": "INITIAL ASSESSMENT: M7.4 verified. Intensity VIII at epicenter. Real-time monitoring of aftershocks in the Alai-Batagram axis.",
            "shakemap": "Shakemap indicates a 45km rupture length. Highest damage probability in northern Batagram and Alai tehsils.",
            "default": "Monitoring seismic sensors and refining impact maps based on incoming data."
        }
    },
    "d1_to_d5": {
        "greeting": "Tech EW monitoring aftershock sequence. Satellite landslide detection active.",
        "actions": ["Daily aftershock trend analysis", "Identify co-seismic landslide clusters", "Verify seismic sensor health in field", "Update Intensity maps with field reports"],
        "responses": {
            "status": "Aftershock frequency remains high. Recorded 3 events >M5.0. Landslide monitoring shows 25 major blockages on secondary roads.",
            "default": "Continuous seismic monitoring to ensure SAR team safety."
        }
    },
    "d5_to_d10": {
        "greeting": "Technical hazard analysis. Dam and bridge seismic stress audit coordination.",
        "actions": ["Seismic stress audit for Tarbela Dam", "Micro-seismic monitoring in Alai", "Geological risk assessment for relief camps"],
        "responses": {
            "status": "Tarbela Dam sensors stable. Micro-seismic units deployed to high-risk zones. Camps verified safe from landslide run-out.",
            "default": "Providing technical risk data to the planning and logistics teams."
        }
    },
    "d10_to_d20": {
        "greeting": "Transition to recovery risk modeling. Revising hazard zoning.",
        "actions": ["Analyze ground motion amplification data", "Draft updated hazard zone maps for Batagram", "Identify safe terrain for transitional housing"],
        "responses": {
            "status": "Ground motion data mapped. Alai tehsil requires higher seismic design factors (Z4+) for reconstruction.",
            "default": "Finalizing data sets for long-term recovery planning."
        }
    },
    "d20_to_d50": {
        "greeting": "Post-EQ technical review. Proposing monitoring network upgrades.",
        "actions": ["Final seismic impact report", "National hazard map revision", "Monitoring station upgrade plan"],
        "responses": {
            "status": "Seismic Impact Report finalized. 5 new permanent monitoring stations proposed for Hazara division.",
            "default": "Concluding technical monitoring phase for the Batagram event."
        }
    }
})

# 2. Ops Wing - Focus: SAR operations
w("ops_wing", "Ops Wing", "🎯", {
    "d_day": {
        "greeting": "Ops Wing NEOC Operational. Deploying NDRT and Urban SAR units to impact zone.",
        "actions": ["Mobilize 2 NDRT teams", "Establish Forward Command Post in Batagram", "Coordinate with Military for heavy airlift", "Sectorize Batagram City for SAR"],
        "responses": {
            "status": "SAR ACTIVE: 4 units on-site. Sectorized search in progress. Focused on collapsed schools and high-density urban clusters.",
            "default": "Managing the tactical response to maximize life-saving interventions."
        }
    },
    "d1_to_d5": {
        "greeting": "Intensive Search and Rescue. Managing international team integration.",
        "actions": ["Manage 15 SAR units (Domestic + Intl)", "Coordinate air medevac for critical injuries", "Publish 6-hourly SitReps", "Task debris clearance for SAR access"],
        "responses": {
            "status": "SAR 70% complete in urban areas. 1,200 casualties confirmed. 600 rescues successful. Focus moving to rural Alai clusters.",
            "default": "Operational tempo remains high to utilize the 72-96 hour 'Golden Window'."
        }
    },
    "d5_to_d10": {
        "greeting": "Transitioning to sustained relief operations. Relief camp oversight.",
        "actions": ["Oversee camp security coordination", "Process field relief requests", "Coordinate airlift for isolated Alai valleys"],
        "responses": {
            "status": "Relief ops dominant. 12 camps established for 45,000 survivors. Supply drops active where roads remain blocked.",
            "default": "Coordinating field operations to ensure sustained survival in disaster zones."
        }
    },
    "d10_to_d20": {
        "greeting": "Scaling down SAR assets. Early recovery coordination.",
        "actions": ["Demobilize SAR units", "Facilitate compensation survey teams", "Plan handover to local recovery authorities"],
        "responses": {
            "status": "International teams demobilizing. Shift to damage survey and compensation validation.",
            "default": "Managing the operational transition from emergency rescue to early recovery."
        }
    },
    "d20_to_d50": {
        "greeting": "Recovery oversight and After-Action coordination.",
        "actions": ["Final SITREP publication", "Consolidated SAR audit", "Lessons learned operational input"],
        "responses": {
            "status": "Ops phase concluding. Finalizing documentation of all field engagements. 100% of target zones verified.",
            "default": "Maintaining oversight of final recovery fieldwork."
        }
    }
})

# 3. Logistics - Focus: Supply Chain
w("logistics", "Logistics", "🚚", {
    "d_day": {
        "greeting": "Logistics Wing activated. Emergency stocks being dispatched from regional warehouses.",
        "actions": ["Dispatch 5k tents from Sihala", "Activate commercial transport contracts", "Establish Mansehra Logistics Hub", "Task fuel tankers for emergency generators"],
        "responses": {
            "status": "HUB STATUS: Mansehra depot initialized. 50 truck fleet ready. KKH blockages being bypassed via secondary routes.",
            "default": "Securing the supply chain to move vital relief goods to the front lines."
        }
    },
    "d1_to_d5": {
        "greeting": "Supply pipeline in full effect. Reaching 'Last Mile' via coordinated hubs.",
        "actions": ["Manage 'Last Mile' delivery to camps", "Coordinate heli-slings for food drops", "Track all inventory via digital portal", "Procure emergency water treatment units"],
        "responses": {
            "status": "LOGS ACTIVE: 10,000 food packs delivered. 3 heli-pads operational for Alai supplies. Inventory digital tracking at 100%.",
            "default": "Moving essential food, water, and non-food items (NFIs) to affected populations."
        }
    },
    "d5_to_d10": {
        "greeting": "Sustained relief logistics. Warehousing and cold chain management.",
        "actions": ["Manage 3 regional relief hubs", "Facilitate donor-contributed aid intake", "Maintain water-bowser supply chain", "Logistics support for field hospitals"],
        "responses": {
            "status": "Supply chain stabilized. 500 tons of flour and 200 tons of pulses delivered to 15 distribution points.",
            "default": "Ensuring the steady flow of life-sustaining supplies during the relief phase."
        }
    },
    "d10_to_d20": {
        "greeting": "Transitioning to recovery logistics. Reconstruction material procurement.",
        "actions": ["Procure corrugated iron sheets", "Contract transport for reconstruction rubble removal", "Audit emergency equipment rentals"],
        "responses": {
            "status": "Procurement for transitional shelter starting. 30,000 CGI sheets ordered. Rubble removal logic in planning.",
            "default": "Pivoting logistics from emergency relief to reconstruction support."
        }
    },
    "d20_to_d50": {
        "greeting": "Stock replenishment and final logistics audit.",
        "actions": ["Replenish national warehouses", "Audit reconstruction supply chain", "Final logistics performance report"],
        "responses": {
            "status": "Audit complete. 65% of national stocks replenished. Master log report submitted to Chairman.",
            "default": "Concluding the emergency logistics operation for Batagram."
        }
    }
})

# 4. DRR - Focus: Hazard Mapping & Build Back Better
w("drr", "Disaster Risk Reduction (DRR)", "🛡️", {
    "d_day": {
        "greeting": "DRR Wing active. Rapid risk and building failure assessment.",
        "actions": ["Deploy risk assessment teams", "Issue aftershock safety guidelines", "Identify hazardous buildings for demolition"],
        "responses": {
            "status": "ASSESSMENT: 45% of surveyed buildings unusable. Red/Yellow tagging started in urban core.",
            "default": "Identifying risks to prevent secondary casualties from collapsing structures."
        }
    },
    "d1_to_d5": {
        "greeting": "Detailed hazard mapping. Camp site safety verification.",
        "actions": ["Mapping landslide hotspots", "Audit shelter sites for seismic safety", "Community risk awareness campaign"],
        "responses": {
            "status": "DRR MAPS: 12 potential landslide zones identified on KKH. All 10 camp sites audited and cleared for safety.",
            "default": "Mapping the evolving hazard landscape to protect survivors and responders."
        }
    },
    "d5_to_d10": {
        "greeting": "Vulnerability analysis for recovery planning. Mainstreaming DRR.",
        "actions": ["District vulnerability report", "Safe reconstruction zone identification", "CBDRM training for camp leaders"],
        "responses": {
            "status": "Vulnerability report identifies 12,000 families in high-risk zones needing relocation or specific Z5 designs.",
            "default": "Ensuring that the recovery plan addresses underlying vulnerabilities."
        }
    },
    "d10_to_d20": {
        "greeting": "Seismic-safe construction training. 'Build Back Better' guidelines.",
        "actions": ["Draft seismic construction protocols", "Train 500 local masons", "Certify transitional housing designs"],
        "responses": {
            "status": "TRAINING: 250 masons certified in seismic-tie beams and safe masonry. Guidelines shared with Infra Audit wing.",
            "default": "Embedding resilience into the reconstruction DNA of Batagram."
        }
    },
    "d20_to_d50": {
        "greeting": "Finalizing the Resilient Batagram Strategy.",
        "actions": ["BBB Strategy for Batagram", "Finalize multi-hazard district plan", "Institutionalize community hazard monitors"],
        "responses": {
            "status": "Resilient Batagram Strategy finalized. Integrated into Provincial DRR agenda.",
            "default": "Concluding the strategic risk reduction framework for the district."
        }
    }
})

# 5. Plans - Focus: Strategy & CRM
w("plans", "Plans Wing", "🗺️", {
    "d_day": {
        "greeting": "Plans Wing — Strategic Coordination initiated. Drafting Crisis Resource Management (CRM) Framework.",
        "actions": ["Develop initial CRM framework", "Coordinate inter-wing resource mapping", "Prepare strategic brief for federal cabinet", "Establish planning liaison with PDMA KP"],
        "responses": {
            "status": "PLANNING: CRM Draft 1 active. Identifying federal-provincial resource gaps. Coordinating airlift priorities.",
            "default": "Focusing on the high-level strategy and resource mobilization for the earthquake response."
        }
    },
    "d1_to_d5": {
        "greeting": "Plans Wing — Refined response strategy. Inter-agency coordination.",
        "actions": ["Update CRM strategic objectives", "Consolidate wing implementation plans", "Identify international aid requirements", "Monitor strategic KPIs"],
        "responses": {
            "status": "STRATEGY: Integrated response plan active. Priority: Reaching isolated high-altitude clusters within 48 hours.",
            "default": "Maintaining strategic alignment across all responding wings."
        }
    },
    "d5_to_d10": {
        "greeting": "Strategic transition to recovery. Needs assessment oversight.",
        "actions": ["Draft Early Recovery Framework", "Strategic brief for donor coordination", "Identify funding gaps for reconstruction"],
        "responses": {
            "status": "RECOVERY PLAN: Multi-sectoral assessment initiated. Estimating $500M reconstruction requirement.",
            "default": "Planning the shift from emergency lifesaving to sustainable recovery."
        }
    },
    "d10_to_d20": {
        "greeting": "Formulating the Reconstruction Master Plan.",
        "actions": ["Consolidate Reconstruction & Rehab (R&R) Framework", "Coordinate international donor conference", "Design M&E system for recovery projects"],
        "responses": {
            "status": "MASTER PLAN: R&R framework in draft. 15 core sectors identified for priority funding.",
            "default": "Building the roadmap for the long-term rebuilding of Batagram."
        }
    },
    "d20_to_d50": {
        "greeting": "Strategic oversight handover and SimEx finalization.",
        "actions": ["Consolidated SimEx final report", "Strategic policy recommendations", "Transition to Reconstruction Authority"],
        "responses": {
            "status": "FINAL STRATEGY: 30 policy improvements identified. Recovery Authority operationalized with our strategy.",
            "default": "Concluding the strategic planning phase of the SimEx."
        }
    }
})

# 6. PCC - Focus: Provincial Coordination
w("pcc", "Provincial Coordination Cell (PCC)", "🏛️", {
    "d_day": {
        "greeting": "PCC active. Facilitating federal support to PDMA KP.",
        "actions": ["Joint Command protocol with PDMA KP", "Mobilize provincial assets via DDMA", "Facilitate federal asset entry permits", "Authorize inter-district aid movement"],
        "responses": {
            "status": "COORDINATION: 24/7 link with KP NEOC. PDMA KP assets moving to Batagram alongside NDMA. Joint briefing protocols active.",
            "default": "Ensuring a unified command structure between Federal and Provincial authorities."
        }
    },
    "d1_to_d5": {
        "greeting": "PCC — Managing bulk resource transfer and inter-provincial support.",
        "actions": ["Monitor federal-to-provincial asset flow", "Coordinate regional mutual aid (Punjab/Sindh to KP)", "Manage NGO field access permissions"],
        "responses": {
            "status": "RESOURCES: Authorized 150 trucks of aid from Punjab for KP distribution. Clearing data sync between NDMA and PDMA dashboard.",
            "default": "Supporting the provincial government in scaling up and managing external aid."
        }
    },
    "d5_to_d10": {
        "greeting": "Provincial capacity auditing and gap bridging.",
        "actions": ["Coordinate high-level Fed-Prov review", "Audit relief distribution at district level", "Resolve inter-departmental logistics disputes"],
        "responses": {
            "status": "PCC STATUS: Resolved 3 logistics bottlenecks at provincial borders. Monitoring equitable distribution across 5 affected tehsils.",
            "default": "Maintaining inter-governmental harmony and operational efficiency."
        }
    },
    "d10_to_d20": {
        "greeting": "PCC — Transition to recovery governance coordination.",
        "actions": ["Coordinate provincial R&R body activation", "Monitor compensation data integrity", "Identify provincial policy gaps in recovery"],
        "responses": {
            "status": "GOVERNANCE: Facilitating biometric data sharing between NADRA and PDMA for compensation disbursements.",
            "default": "Ensuring the provincial recovery authority has the federal support it needs."
        }
    },
    "d20_to_d50": {
        "greeting": "PCC — Final coordination audit and R&R handover.",
        "actions": ["Final coordination performance report", "Audit utilization of federal grants by province", "Archive provincial case studies"],
        "responses": {
            "status": "Final report submitted. Coordination flow rated 'High Efficiency'. Audit confirms PKR 10B utilized for relief.",
            "default": "Concluding inter-governmental coordination for the Batagram response."
        }
    }
})

# 7. Tech E & M - Focus: Electronics and Communication Channels (REVISIONS)
w("tech_e_m", "Tech E & M", "⚙️", {
    "d_day": {
        "greeting": "Technical Equipment and Maintenance (Tech E&M) Wing mobilized. Restoring NEOC connectivity and radio networks.",
        "actions": ["Deploy mobile satellite comms trailers", "Activate emergency VHF/HF radio network", "Technical check of Batagram NEOC servers", "Establish backup data links via Starlink/Satellite"],
        "responses": {
            "status": "TECH STATUS: Primary fiber link cut. Deploying 3 SATCOM units. VHF repeaters being re-aligned for full district coverage.",
            "comms": "Radio network active on 155.450MHz. Satellite backup at 90% stability. Establishing ICT-hub for SAR teams.",
            "default": "Ensuring robust communication channels and technical equipment functionality for the response."
        }
    },
    "d1_to_d5": {
        "greeting": "Tech E&M — Sustaining communication backbone. Equipment maintenance.",
        "actions": ["Maintain 24/7 radio dispatch for SAR ops", "Repair damaged field comms equipment", "Technical support for digital SitRep tools", "Optimize satellite bandwidth for video reconnaissance"],
        "responses": {
            "status": "MAINTENANCE: 45 handheld radios repaired. Satellite bandwidth tripled for real-time drone feeds. NEOC technical uptime 99.8%.",
            "default": "Keeping the technical systems running so coordination remains seamless."
        }
    },
    "d5_to_d10": {
        "greeting": "Advanced technical systems deployment. Information infrastructure integrity.",
        "actions": ["Deploy solar-powered radio repeaters", "Technical audit of camp data centers", "Establish public information kiosks (low-tech digital)"],
        "responses": {
            "status": "TECH UPGRADE: 5 solar repeaters deployed to Alai for isolated SAR comms. District ICT hub providing internet for relief agencies.",
            "default": "Maintaining specialized electronic equipment and long-range communication links."
        }
    },
    "d10_to_d20": {
        "greeting": "Transition to permanent technical infrastructure repair.",
        "actions": ["Support PTCL for permanent fiber repair", "Upgrade district NEOC server infrastructure", "Maintenance of biometric compensation terminals"],
        "responses": {
            "status": "RESTORATION: Permanent fiber optic link 60% repaired. Biometric terminals technical support 24/7. ICT systems being hardened.",
            "default": "Pivoting from emergency comms to permanent technical network restoration."
        }
    },
    "d20_to_d50": {
        "greeting": "Final technical audit and equipment overhaul.",
        "actions": ["Final ICT performance report", "Equipment maintenance and warehouse return", "Proposing future technical redundancies"],
        "responses": {
            "status": "Final report highlights need for 3 extra satellite trailers. 100% of field electronics serviced and returned to central pool.",
            "default": "Concluding the technical equipment and maintenance mission for Batagram."
        }
    }
})

# 8. Military/Media - Focus: Media & Information
w("military_media", "Regional Military and Media Wing", "📢", {
    "d_day": {
        "greeting": "Military & Media Wing active. Managing the information space and military SAR liaison.",
        "actions": ["Broadcast initial public safety bulletins", "ISPR coordination for military SAR assets", "Activate social media rumor-control team", "Hourly media SitReps"],
        "responses": {
            "status": "INFO OPS: Media center established. Military Helis integrated into Ops plan. Countering rumors of dam breach on social media.",
            "default": "Managing the public narrative and coordinating high-value military assets."
        }
    },
    "d1_to_d5": {
        "greeting": "Military & Media — Information dominance and public awareness.",
        "actions": ["Organize pool media visits to SAR sectors", "Coordinate military airlift for heavy gear", "Run radio safety broadcasts", "Fact-check social media reports"],
        "responses": {
            "status": "MEDIA: 80 positive national placements. ISPR briefing held at 14:00. Radio outreach reaching 85% of affected district via FM transponders.",
            "default": "Ensuring accurate information flow while showcasing the response effort."
        }
    },
    "d5_to_d10": {
        "greeting": "Media focus shifting to relief visibility and donor engagement.",
        "actions": ["Produce human-interest documentary content", "Coordinate VIP and Donor media tours", "Launch 'Hope after Quake' campaign"],
        "responses": {
            "status": "VISIBILITY: Highlighting civil-military synergy. Donor documentary 50% filmed. Managing expectations via radio broadcasts.",
            "default": "Maintaining public and international support for the ongoing relief operation."
        }
    },
    "d10_to_d20": {
        "greeting": "Informing the recovery phase. Compensation awareness.",
        "actions": ["Campaign on 'Biometric Payment' procedures", "Broadcast construction safety standards", "Transparency monitoring via media"],
        "responses": {
            "status": "AWARENESS: Compensation explainer videos reaching 1M views. Focus: 'Build resilience, build seismic-safe'.",
            "default": "Using media channels to support orderly transition into the recovery phase."
        }
    },
    "d20_to_d50": {
        "greeting": "Post-event documentation and institutional memory.",
        "actions": ["Final communications audit report", "Archive documented human-interest stories", "Produce 'Lessons Learned' media brief"],
        "responses": {
            "status": "METRICS: Final media report confirms 92% positive sentiment. All communication goals achieved successfully.",
            "default": "Preserving the story of the Batagram response for future exercises."
        }
    }
})

# 9. NIDM - Focus: Training & Documentation
w("nidm", "National Institute of Disaster Management (NIDM)", "🎓", {
    "d_day": {
        "greeting": "NIDM active. Deploying real-time observers to document high-intensity response.",
        "actions": ["Observers embedded in NEOC", "Activate training for camp volunteers", "Real-time documentation of decision-making"],
        "responses": {
            "status": "OBSERVATION: 4 teams on-site. Documenting inter-wing coordination. Identifying immediate training needs in field command.",
            "default": "Capturing live institutional learning during the most critical 72 hours."
        }
    },
    "d1_to_d5": {
        "greeting": "Field training and coordination auditing.",
        "actions": ["Conduct first-aid and camp training for locals", "Interim report on SAR coordination bottlenecks", "Document relief distribution logistics"],
        "responses": {
            "status": "TRAINING: 150 local volunteers trained. Interim report highlights need for better data sync at transit points.",
            "default": "Improving the live response through documentation and targeted field training."
        }
    },
    "d5_to_d10": {
        "greeting": "Mid-exercise After-Action Review (AAR) and relief audit.",
        "actions": ["Host mid-term lessons learned workshop", "Audit relief distribution efficiency", "Document civil-military coordination patterns"],
        "responses": {
            "status": "AAR: Mid-term review complete. Identified 12 immediate coordination improvements. Relief audit 80% finished.",
            "default": "Translating field observations into organizational improvements during the exercise."
        }
    },
    "d10_to_d20": {
        "greeting": "Developing recovery-phase capacity building programs.",
        "actions": ["Formulate training for recovery authorities", "Document transition challenges and best practices", "Publish interim AAR report"],
        "responses": {
            "status": "DATA: AAR Draft 1 submitted. Recovery workshop for PDMA and District officials scheduled.",
            "default": "Preparing the human resource capacity for long-term reconstruction."
        }
    },
    "d20_to_d50": {
        "greeting": "Final After-Action Report and curriculum integration.",
        "actions": ["Final Comprehensive AAR", "Submit policy-change recommendations", "Update National SimEx curriculum"],
        "responses": {
            "status": "FINAL REPORT: 300-page AAR finalized. Lessons integrated into the 2026/27 national training cycle.",
            "default": "Closing the loop on institutional learning and future preparedness."
        }
    }
})

# 10. Infra Audit - Focus: Structural Integrity
w("infra_audit", "Infra Audit and Project Development Wing", "🏗️", {
    "d_day": {
        "greeting": "Infra Audit Wing active. Structural assessment teams deployed to Batagram.",
        "actions": ["Assess 10 critical public buildings", "Audit Thakot Bridge structural integrity", "Cooperate with PEC for volunteer engineers", "Tag buildings as Red/Yellow/Green for safety"],
        "responses": {
            "status": "AUDIT: DHQ Hospital assessed; courtyard is safe but wing B is Red-tagged. Thakot bridge verified as stable for trucks.",
            "default": "Performing immediate structural checks to identify safe spaces for emergency operations."
        }
    },
    "d1_to_d5": {
        "greeting": "Sector-wise Infrastructure Damage Assessment (IDA) in progress.",
        "actions": ["Audit 500+ buildings in city center", "Forensic analysis of structural failures", "Support Tech E&M with cabling duct checks"],
        "responses": {
            "status": "IDA: 350 houses surveyed. 60% Red-tagged. High masonry failure rate observed. Engineering teams mapping collapse patterns.",
            "default": "Providing clear safety signals to the community through systematic building tagging."
        }
    },
    "d5_to_d10": {
        "greeting": "Consolidating district-wide damage data for reconstruction modeling.",
        "actions": ["Detailed Damage Assessment (DDA) report", "Infrastructure reconstruction cost modeling", "Structural check of all relief camp sites"],
        "responses": {
            "status": "DATA: Preliminary damage estimate: PKR 85 Billion. All 12 camp shelters audited and certified safe.",
            "default": "Turning damage data into a financially viable reconstruction roadmap."
        }
    },
    "d10_to_d20": {
        "greeting": "Developing the high-priority reconstruction project pipeline.",
        "actions": ["Design 15 priority public infra projects", "Standardize seismic-safe building protocols", "Engineering audit of transitional learning centers"],
        "responses": {
            "status": "PROJECTS: 15 schooling and health facility tenders ready for funding. Protocols for Z4+ Zonation finalized.",
            "default": "Laying the technical engineering foundation for the 'Build Back Better' phase."
        }
    },
    "d20_to_d50": {
        "greeting": "Final Infrastructure Impact Report and Handover.",
        "actions": ["Final Reconstruction Master Plan (Engineering)", "Institutionalize safety audit protocols", "Submit regional seismic vulnerability audit"],
        "responses": {
            "status": "FINAL ENGINEERING: Master plan approved. PKR 95B project pipeline finalized for donor conference.",
            "default": "Concluding the engineering audit and project development phase."
        }
    }
})


with open("data/templates/wing_responses.json", "w", encoding="utf-8") as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("✓ Updated wing_responses.json (v3) created:")
print(f"  Focus: Pure Earthquake + Corrected Tech E&M focus")
print(f"  Wings: {len(data['wings'])}")
for wid, wd in data["wings"].items():
    print(f"  - {wid}: {len(wd['phases'])} phases")
