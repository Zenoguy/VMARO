import boto3
import json
import os
from dotenv import load_dotenv

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
print("started the process...")
load_dotenv()

BUCKET = os.getenv("S3_BUCKET")
REGION = os.getenv("AWS_REGION")

print("loaded the bucket...")
if not BUCKET:
    raise ValueError("S3_BUCKET not found in .env")

print(f"Using bucket: {BUCKET}")
print(f"Region: {REGION}")

# --------------------------------------------------
# Create S3 client
# --------------------------------------------------

s3 = boto3.client("s3", region_name=REGION)

# --------------------------------------------------
# Tree Paths
# --------------------------------------------------

TREE_PATHS = [

# MEDICAL
"medical/cardiology/heart_disease/papers.json",
"medical/cardiology/cardiac_surgery/papers.json",
"medical/pulmonology/lung_disease/papers.json",
"medical/pulmonology/respiratory_failure/papers.json",
"medical/neurology/neurodegenerative_disease/papers.json",
"medical/neurology/brain_imaging/papers.json",
"medical/oncology/cancer_diagnosis/papers.json",
"medical/oncology/cancer_therapy/papers.json",

# MATHEMATICS
"mathematics/algebra/group_theory/papers.json",
"mathematics/algebra/linear_algebra/papers.json",
"mathematics/analysis/real_analysis/papers.json",
"mathematics/analysis/complex_analysis/papers.json",
"mathematics/geometry/topology/papers.json",
"mathematics/geometry/differential_geometry/papers.json",
"mathematics/applied_mathematics/optimization/papers.json",
"mathematics/applied_mathematics/numerical_methods/papers.json",

# PHYSICS
"physics/general_physics/mechanics/papers.json",
"physics/general_physics/optics/papers.json",
"physics/general_physics/fluid_mechanics/papers.json",
"physics/general_physics/aerodynamics/papers.json",
"physics/general_physics/electromagnetism/papers.json",
"physics/general_physics/thermodynamics/papers.json",

"physics/quantum_physics/quantum_mechanics/papers.json",
"physics/quantum_physics/quantum_computing/papers.json",
"physics/quantum_physics/condensed_matter/papers.json",
"physics/quantum_physics/particle_physics/papers.json",

# CHEMISTRY
"chemistry/organic_chemistry/organic_synthesis/papers.json",
"chemistry/organic_chemistry/polymer_chemistry/papers.json",
"chemistry/inorganic_chemistry/coordination_chemistry/papers.json",
"chemistry/inorganic_chemistry/catalysis/papers.json",
"chemistry/physical_chemistry/quantum_chemistry/papers.json",
"chemistry/physical_chemistry/spectroscopy/papers.json",

# COMPUTATIONAL SCIENCE
"computational_science/artificial_intelligence/reasoning/papers.json",
"computational_science/artificial_intelligence/autonomous_systems/papers.json",

"computational_science/machine_learning/supervised_learning/papers.json",
"computational_science/machine_learning/deep_learning/papers.json",
"computational_science/machine_learning/reinforcement_learning/papers.json",

"computational_science/data_structures/trees_graphs/papers.json",
"computational_science/data_structures/hashing/papers.json",

"computational_science/algorithms/graph_algorithms/papers.json",
"computational_science/algorithms/optimization_algorithms/papers.json",

# FINANCE
"finance/quantitative_finance/derivative_pricing/papers.json",
"finance/quantitative_finance/portfolio_optimization/papers.json",
"finance/financial_markets/market_prediction/papers.json",
"finance/financial_markets/high_frequency_trading/papers.json",
"finance/fintech/blockchain_finance/papers.json",
"finance/fintech/decentralized_finance/papers.json"
]

# --------------------------------------------------
# Initialize Tree
# --------------------------------------------------

def init_tree():

    created = 0
    skipped = 0

    for path in TREE_PATHS:

        try:

            # check if file already exists
            s3.head_object(Bucket=BUCKET, Key=path)

            print(f"Exists: {path}")
            skipped += 1

        except:

            data = {"papers": []}

            s3.put_object(
                Bucket=BUCKET,
                Key=path,
                Body=json.dumps(data, indent=2)
            )

            print(f"Created: {path}")
            created += 1

    print("\nInitialization complete.")
    print(f"Created: {created}")
    print(f"Skipped: {skipped}")


if __name__ == "__main__":
    init_tree()