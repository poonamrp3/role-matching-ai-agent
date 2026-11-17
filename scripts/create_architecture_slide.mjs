import fs from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { Presentation, PresentationFile } from "@oai/artifact-tool";

const workspaceDir = "/Users/poonampawar/Documents/ChatGPT/CrowdDoing_Roles_Processing";
const skillDir = "/Users/poonampawar/.codex/plugins/cache/openai-primary-runtime/presentations/26.1116.12020/skills/presentations";
const buildDir = path.join(workspaceDir, ".presentation-build");
const outputDir = path.join(workspaceDir, "output");
const finalPath = path.join(outputDir, "role_matching_architecture_diagram_v3.pptx");
const draftPath = path.join(buildDir, "role_matching_architecture_diagram_draft.pptx");

async function writeBlob(filePath, blob) {
  await fs.writeFile(filePath, new Uint8Array(await blob.arrayBuffer()));
}

function addText(slide, text, position, style = {}) {
  const shape = slide.shapes.add({
    geometry: "textbox",
    position,
    fill: "none",
    line: { style: "solid", fill: "none", width: 0 },
  });
  shape.text = text;
  shape.text.style = style;
  return shape;
}

function addStep(slide, label, position, { fill, line, color = "#F8FAFC" }) {
  const shape = slide.shapes.add({
    geometry: "roundRect",
    position,
    fill,
    line: { style: "solid", fill: line, width: 1.25 },
    borderRadius: "rounded-xl",
  });
  shape.text = label;
  shape.text.style = {
    fontSize: "15pt",
    fontFamily: "Aptos",
    bold: true,
    color,
    alignment: "center",
    verticalAlignment: "middle",
    marginLeft: 10,
    marginRight: 10,
    marginTop: 8,
    marginBottom: 8,
  };
  return shape;
}

async function main() {
  await fs.mkdir(buildDir, { recursive: true });
  await fs.mkdir(outputDir, { recursive: true });

  const presentation = Presentation.create({ slideSize: { width: 1280, height: 720 } });
  const slide = presentation.slides.add();
  slide.background.fill = "#071525";

  addText(slide, "Role-Matching Agent Architecture", { left: 64, top: 38, width: 760, height: 46 }, {
    fontSize: "32pt", fontFamily: "Aptos Display", bold: true, color: "#F8FAFC",
  });
  addText(slide, "Indexed ESCO role knowledge supports bounded candidate-to-role retrieval", { left: 66, top: 88, width: 900, height: 24 }, {
    fontSize: "14pt", fontFamily: "Aptos", color: "#A9C0D2",
  });

  const laneLeft = 64;
  const laneWidth = 1152;
  slide.shapes.add({
    geometry: "roundRect",
    position: { left: laneLeft, top: 145, width: laneWidth, height: 188 },
    fill: "#0B2135",
    line: { style: "solid", fill: "#1E4059", width: 1.2 },
    borderRadius: "rounded-xl",
  });
  slide.shapes.add({
    geometry: "roundRect",
    position: { left: laneLeft, top: 377, width: laneWidth, height: 267 },
    fill: "#0B2135",
    line: { style: "solid", fill: "#1E4059", width: 1.2 },
    borderRadius: "rounded-xl",
  });

  addText(slide, "INDEXING PIPELINE", { left: 88, top: 164, width: 250, height: 24 }, {
    fontSize: "13pt", fontFamily: "Aptos", bold: true, color: "#66E3CD",
  });
  addText(slide, "QUERY PIPELINE", { left: 88, top: 396, width: 250, height: 24 }, {
    fontSize: "13pt", fontFamily: "Aptos", bold: true, color: "#66E3CD",
  });

  const indexingLabels = [
    "ESCO roles\nand skills",
    "Normalize\nstructured data",
    "Retrieval\ndocuments",
    "Nomic\nembeddings",
    "Qdrant active\nrole index",
  ];
  const indexingSteps = [];
  const indexY = 222;
  const indexW = 168;
  const indexH = 72;
  const indexGap = 58;
  for (let i = 0; i < indexingLabels.length; i += 1) {
    indexingSteps.push(addStep(slide, indexingLabels[i], {
      left: 94 + i * (indexW + indexGap), top: indexY, width: indexW, height: indexH,
    }, { fill: "#12364C", line: "#2F637E" }));
  }
  for (let i = 0; i < indexingSteps.length - 1; i += 1) {
    const connector = slide.shapes.connect(indexingSteps[i], indexingSteps[i + 1], {
      kind: "straight", fromSide: "right", toSide: "left",
      line: { style: "solid", fill: "#66E3CD", width: 2 },
      tail: { type: "arrow", width: "med", length: "med" },
    });
    connector.bringToFront();
  }

  const queryLabels = [
    "Recruiter\nprompt",
    "Query\nintent &\nguardrails",
    "Gmail\nsubmission\ntool",
    "Candidate text\n& Nomic\nvector",
    "Qdrant role\nretrieval",
    "Response plan\nLLM",
    "UI response",
  ];
  const querySteps = [];
  const queryY = 466;
  const queryW = 142;
  const queryH = 88;
  const queryGap = 19;
  for (let i = 0; i < queryLabels.length; i += 1) {
    querySteps.push(addStep(slide, queryLabels[i], {
      left: 86 + i * (queryW + queryGap), top: queryY, width: queryW, height: queryH,
    }, { fill: i === 6 ? "#195649" : "#12364C", line: i === 6 ? "#54C7AD" : "#2F637E" }));
  }
  for (let i = 0; i < querySteps.length - 1; i += 1) {
    const connector = slide.shapes.connect(querySteps[i], querySteps[i + 1], {
      kind: "straight", fromSide: "right", toSide: "left",
      line: { style: "solid", fill: "#66E3CD", width: 1.7 },
      tail: { type: "arrow", width: "sm", length: "sm" },
    });
    connector.bringToFront();
  }

  addText(slide, "Local processing: OAuth token store, candidate text, embeddings, and Qdrant remain outside the UI", { left: 88, top: 588, width: 1050, height: 22 }, {
    fontSize: "11pt", fontFamily: "Aptos", color: "#9AB0C1",
  });

  await writeBlob(path.join(buildDir, "architecture-slide.png"), await presentation.export({ slide, format: "png", scale: 1.5 }));
  await (await PresentationFile.exportPptx(presentation)).save(draftPath);

  const { finalizePresentation } = await import(pathToFileURL(
    path.join(skillDir, "container_tools", "artifact_tool_utils.mjs"),
  ).href);
  await finalizePresentation({
    workspaceDir,
    candidatePath: draftPath,
    finalPath,
    pythonExecutable: process.env.RUNTIME_PYTHON,
    integrityValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_package_integrity.py"),
    layoutValidatorPath: path.join(skillDir, "container_tools", "inspect_presentation_layout_geometry.py"),
    layoutArgs: ["--expected-slide-size-emu", "12192000,6858000", "--validate-heading-fit"],
    explicitTotalSlideCount: 1,
    requiredNativeTableOwnerSlides: [],
    fontPolicy: { basis: "design", families: ["Arial"] },
    verifyArtifactToolImport: true,
    receiptPath: path.join(buildDir, "architecture-slide-v3.validation.json"),
  });
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
