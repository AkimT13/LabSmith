"use client";

import { useEffect, useMemo } from "react";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Box3, Color, GridHelper, type BufferGeometry, Vector3 } from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

interface StlViewerProps {
  geometry: BufferGeometry;
}

export function StlViewer({ geometry }: StlViewerProps) {
  const prepared = useMemo(() => prepareGeometry(geometry), [geometry]);

  useEffect(() => {
    return () => {
      prepared.geometry.dispose();
    };
  }, [prepared.geometry]);

  const cameraDistance = Math.max(prepared.radius * 3, 24);
  const gridSize = Math.max(prepared.radius * 3, 30);

  return (
    <Canvas
      className="h-full w-full"
      camera={{
        position: [cameraDistance, cameraDistance * 0.7, cameraDistance],
        fov: 42,
        near: 0.1,
        far: Math.max(cameraDistance * 8, 500),
      }}
      gl={{ antialias: true }}
    >
      <color attach="background" args={["#f8fafc"]} />
      <ambientLight intensity={0.65} />
      <directionalLight position={[20, 35, 18]} intensity={1.4} />
      <directionalLight position={[-14, 12, -18]} intensity={0.45} />

      <group rotation={[-Math.PI / 2, 0, 0]}>
        <mesh geometry={prepared.geometry} castShadow receiveShadow>
          <meshStandardMaterial
            color={new Color("#8aa4b8")}
            metalness={0.18}
            roughness={0.48}
          />
        </mesh>
      </group>

      <ViewerGrid size={gridSize} y={-prepared.radius} />
      <CameraControls />
    </Canvas>
  );
}

function CameraControls() {
  const { camera, gl } = useThree();
  const controls = useMemo(() => {
    const nextControls = new OrbitControls(camera, gl.domElement);
    nextControls.enableDamping = true;
    nextControls.dampingFactor = 0.08;
    nextControls.target.set(0, 0, 0);
    nextControls.update();
    return nextControls;
  }, [camera, gl.domElement]);

  useEffect(() => {
    return () => {
      controls.dispose();
    };
  }, [controls]);

  useFrame(() => {
    controls.update();
  });

  return null;
}

function ViewerGrid({ size, y }: { size: number; y: number }) {
  const grid = useMemo(() => {
    const divisions = Math.max(10, Math.round(size / 2));
    const helper = new GridHelper(size, divisions, "#94a3b8", "#e2e8f0");
    helper.position.y = y;
    return helper;
  }, [size, y]);

  useEffect(() => {
    return () => {
      grid.geometry.dispose();
      if (Array.isArray(grid.material)) {
        grid.material.forEach((material) => material.dispose());
      } else {
        grid.material.dispose();
      }
    };
  }, [grid]);

  return <primitive object={grid} />;
}

function prepareGeometry(sourceGeometry: BufferGeometry) {
  const geometry = sourceGeometry.clone();
  geometry.computeVertexNormals();
  geometry.computeBoundingBox();

  const box = geometry.boundingBox ?? new Box3();
  const center = new Vector3();
  box.getCenter(center);
  geometry.translate(-center.x, -center.y, -center.z);
  geometry.computeBoundingSphere();

  return {
    geometry,
    radius: geometry.boundingSphere?.radius || 10,
  };
}
