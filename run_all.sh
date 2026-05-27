#ALL
python -m agents.agent1_analyst --output evaluation/results/BPMNEvidence.json --diagram evaluation/dataset/diagram_001.json --checklist evaluation/dataset/Checklist\ completo\ -\ Modelagem\ 1\ -\ Básico.csv;
python -m agents.agent2_evaluator;
read -p "Revise o BPMNAssessment.json gerado, aplicando a penalidade correta em cada assessment. Utilize a flag review para auxiliar.\n Pressione Enter para continuar...";
python -m agents.agent3_feedback --output evaluation/results/BPMNFeedback.json --diagram evaluation/dataset/diagram_001.json --enunciado evaluation/dataset/Instruções.txt --assessment evaluation/results/BPMNAssessment.json
