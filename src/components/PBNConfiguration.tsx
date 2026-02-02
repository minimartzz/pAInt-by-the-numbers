"use client";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { NativeSelect } from "@/components/ui/native-select";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ChevronRightIcon } from "lucide-react";
import { useState } from "react";

const PBNConfiguration = () => {
  const [activeTab, setActiveTab] = useState("default");
  const numColours = Array.from({ length: 30 }, (_, i) => i + 1);

  return (
    <div className="self-start mt-6">
      {/* Configuration header */}
      <h2 className="text-xl font-bold text-gray-700">Canvas Configurations</h2>
      <Tabs
        defaultValue="default"
        className="gap-4 my-2"
        onValueChange={setActiveTab}
      >
        <TabsList className="bg-accent-soft gap-2">
          <TabsTrigger key="default" value="default">
            Default
          </TabsTrigger>
          {/* IMPROVEMENT: OpenAI disabled for now */}
          <TabsTrigger key="openai" value="openai" disabled={true}>
            OpenAI
          </TabsTrigger>
        </TabsList>
      </Tabs>

      <div className="flex flex-col pt-2">
        {/* Main Configurations */}
        <div className="flex gap-x-20">
          <div className="flex flex-col gap-y-2">
            <Label htmlFor="k_colours" className="text-gray-600 gap-1">
              Number of Colours <span className="text-destructive">*</span>
            </Label>
            <NativeSelect
              id="k_colours"
              name="k_colours"
              defaultValue={20}
              className="bg-white"
              required
            >
              {numColours.map((num) => (
                <option key={num} value={num}>
                  {num}
                </option>
              ))}
            </NativeSelect>
          </div>
          <div className="flex flex-col gap-y-2">
            <Label htmlFor="encoding" className="text-gray-600 gap-1">
              Colour Encoding <span className="text-destructive">*</span>
            </Label>
            <NativeSelect
              id="encoding"
              name="encoding"
              defaultValue={"BGR"}
              className="bg-white"
              required
            >
              <option value="BGR">BGR</option>
              <option value="RGB">RGB</option>
            </NativeSelect>
          </div>
          <div className="flex flex-col gap-y-2">
            <Label htmlFor="filename" className="text-gray-600 gap-1">
              Filename (optional)
            </Label>
            <Input
              id="filename"
              name="filename"
              type="text"
              placeholder="filename"
              className="w-80 bg-white"
            />
          </div>
        </div>
        {/* OpenAI Configurations */}
        {activeTab === "openai" && (
          <div className="flex flex-col gap-y-2 mt-3">
            <Label htmlFor="openai_key" className="text-gray-600 gap-1">
              OpenAI Key <span className="text-destructive">*</span>
            </Label>
            <Input
              id="openapi_key"
              name="openapi_key"
              type="text"
              placeholder="OpenAI API Key"
              className="w-full max-w-xl bg-white"
            />
          </div>
        )}

        {/* Advanced Configurations */}
        <Collapsible title="Advanced Configurations">
          <CollapsibleTrigger className="flex pt-7 items-center justify-between gap-4 font-medium text-gray-500 text-sm">
            <span>Advanced Configurations</span>
            <ChevronRightIcon className="size-4 transition-transform in-data-[state=open]:rotate-90 text-gray-500" />
          </CollapsibleTrigger>
          <CollapsibleContent>
            <div className="flex flex-col gap-y-3">
              {activeTab === "default" && (
                <div className="space-y-2">
                  <h3 className="pt-2 text-sm text-gray-500">
                    Superpixel Segmentation Configurations
                  </h3>
                  <div className="flex gap-x-20">
                    <div className="flex flex-col gap-y-2">
                      <Label htmlFor="segments" className="text-gray-400 gap-1">
                        Segments
                      </Label>
                      <Input
                        id="segments"
                        name="segments"
                        type="number"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        defaultValue={200}
                        className="w-30 bg-white"
                      />
                    </div>
                    <div className="flex flex-col gap-y-2">
                      <Label
                        htmlFor="compactness"
                        className="text-gray-400 gap-1"
                      >
                        Compactness
                      </Label>
                      <Input
                        id="compactness"
                        name="compactness"
                        type="number"
                        inputMode="numeric"
                        pattern="[0-9]*"
                        defaultValue={10}
                        className="w-30 bg-white"
                      />
                    </div>
                    <div className="flex flex-col gap-y-2">
                      <Label htmlFor="sigma" className="text-gray-400 gap-1">
                        Sigma (0.1-1)
                      </Label>
                      <Input
                        id="sigma"
                        name="sigma"
                        type="input"
                        inputMode="numeric"
                        defaultValue={1}
                        className="w-30 bg-white"
                      />
                    </div>
                  </div>
                </div>
              )}
              <div className="space-y-2">
                <h3 className="pt-2 text-sm text-gray-500">Canvas Creation</h3>
                <div className="flex gap-x-20">
                  <div className="flex flex-col gap-y-2">
                    <Label htmlFor="min_area" className="text-gray-400 gap-1">
                      Minimum Area Ratio
                    </Label>
                    <Input
                      id="min_area"
                      name="min_area"
                      type="input"
                      inputMode="numeric"
                      defaultValue={0.0001}
                      className="w-30 bg-white"
                    />
                  </div>
                </div>
              </div>
            </div>
          </CollapsibleContent>
        </Collapsible>
      </div>
    </div>
  );
};

export default PBNConfiguration;
