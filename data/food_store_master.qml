<!DOCTYPE qgis PUBLIC 'http://mrcc.com/qgis.dtd' 'SYSTEM'>
<qgis version="3.34.0" styleCategories="Symbology|Labeling">
  <renderer-v2 type="categorizedSymbol" attr="cat" forceraster="0" enableorderby="0" symbollevels="0" referencescale="-1">
    <categories>
      <category value="supermarket" symbol="0" label="食品スーパー・各種食料品 (supermarket)" render="true" type="string"/>
      <category value="convenience" symbol="1" label="コンビニ (convenience)" render="true" type="string"/>
      <category value="drugstore" symbol="2" label="ドラッグストア (drugstore)" render="true" type="string"/>
      <category value="fresh_food" symbol="3" label="生鮮専門店 (fresh_food)" render="true" type="string"/>
      <category value="" symbol="4" label="その他/未分類" render="true" type="string"/>
    </categories>
    <symbols>
      <symbol type="marker" name="0" alpha="1" clip_to_extent="1" frame_rate="10" force_rhr="0" is_animated="0">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0" id="">
          <Option type="Map">
            <Option name="color" type="QString" value="225,87,89,255"/>
            <Option name="joinstyle" type="QString" value="bevel"/>
            <Option name="name" type="QString" value="circle"/>
            <Option name="outline_color" type="QString" value="255,255,255,180"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="outline_width" type="QString" value="0.2"/>
            <Option name="outline_width_unit" type="QString" value="MM"/>
            <Option name="scale_method" type="QString" value="diameter"/>
            <Option name="size" type="QString" value="2.2"/>
            <Option name="size_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="marker" name="1" alpha="1" clip_to_extent="1" frame_rate="10" force_rhr="0" is_animated="0">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0" id="">
          <Option type="Map">
            <Option name="color" type="QString" value="78,121,167,255"/>
            <Option name="joinstyle" type="QString" value="bevel"/>
            <Option name="name" type="QString" value="circle"/>
            <Option name="outline_color" type="QString" value="255,255,255,180"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="outline_width" type="QString" value="0.2"/>
            <Option name="outline_width_unit" type="QString" value="MM"/>
            <Option name="scale_method" type="QString" value="diameter"/>
            <Option name="size" type="QString" value="2.2"/>
            <Option name="size_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="marker" name="2" alpha="1" clip_to_extent="1" frame_rate="10" force_rhr="0" is_animated="0">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0" id="">
          <Option type="Map">
            <Option name="color" type="QString" value="89,161,79,255"/>
            <Option name="joinstyle" type="QString" value="bevel"/>
            <Option name="name" type="QString" value="circle"/>
            <Option name="outline_color" type="QString" value="255,255,255,180"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="outline_width" type="QString" value="0.2"/>
            <Option name="outline_width_unit" type="QString" value="MM"/>
            <Option name="scale_method" type="QString" value="diameter"/>
            <Option name="size" type="QString" value="2.2"/>
            <Option name="size_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="marker" name="3" alpha="1" clip_to_extent="1" frame_rate="10" force_rhr="0" is_animated="0">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0" id="">
          <Option type="Map">
            <Option name="color" type="QString" value="176,122,161,255"/>
            <Option name="joinstyle" type="QString" value="bevel"/>
            <Option name="name" type="QString" value="circle"/>
            <Option name="outline_color" type="QString" value="255,255,255,180"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="outline_width" type="QString" value="0.2"/>
            <Option name="outline_width_unit" type="QString" value="MM"/>
            <Option name="scale_method" type="QString" value="diameter"/>
            <Option name="size" type="QString" value="2.2"/>
            <Option name="size_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
      <symbol type="marker" name="4" alpha="1" clip_to_extent="1" frame_rate="10" force_rhr="0" is_animated="0">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0" id="">
          <Option type="Map">
            <Option name="color" type="QString" value="150,150,150,255"/>
            <Option name="joinstyle" type="QString" value="bevel"/>
            <Option name="name" type="QString" value="circle"/>
            <Option name="outline_color" type="QString" value="255,255,255,180"/>
            <Option name="outline_style" type="QString" value="solid"/>
            <Option name="outline_width" type="QString" value="0.2"/>
            <Option name="outline_width_unit" type="QString" value="MM"/>
            <Option name="scale_method" type="QString" value="diameter"/>
            <Option name="size" type="QString" value="2.2"/>
            <Option name="size_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
    </symbols>
    <source-symbol>
      <symbol type="marker" name="0" alpha="1" clip_to_extent="1" frame_rate="10" force_rhr="0" is_animated="0">
        <layer class="SimpleMarker" enabled="1" locked="0" pass="0" id="">
          <Option type="Map">
            <Option name="color" type="QString" value="190,190,190,255"/>
            <Option name="name" type="QString" value="circle"/>
            <Option name="outline_width" type="QString" value="0.2"/>
            <Option name="size" type="QString" value="2"/>
            <Option name="size_unit" type="QString" value="MM"/>
          </Option>
        </layer>
      </symbol>
    </source-symbol>
  </renderer-v2>
  <blendMode>0</blendMode>
  <featureBlendMode>0</featureBlendMode>
  <labeling type="simple">
    <settings calloutType="simple">
      <text-style fieldName="name" isExpression="0" fontFamily="Open Sans" fontSize="8" fontSizeUnit="Point" textColor="50,50,50,255" textOpacity="1" multilineHeight="1" allowHtml="0" blendMode="0" capitalization="0" fontLetterSpacing="0" fontWordSpacing="0" fontItalic="0" fontWeight="50" fontStrikeout="0" fontUnderline="0" namedStyle="Regular">
        <families/>
        <text-buffer bufferDraw="1" bufferSize="1" bufferSizeUnits="MM" bufferColor="255,255,255,255" bufferOpacity="1" bufferJoinStyle="128" bufferNoFill="1"/>
        <text-mask maskEnabled="0"/>
        <background enabled="0"/>
        <shadow shadowDraw="0"/>
        <dd_properties>
          <Option type="Map">
            <Option name="name" type="QString" value=""/>
            <Option name="properties"/>
            <Option name="type" type="QString" value="collection"/>
          </Option>
        </dd_properties>
      </text-style>
      <text-format addDirectionSymbol="0" placeDirectionSymbol="0" formatNumbers="0" decimals="3" plussign="0" multilineAlign="3" reverseDirectionSymbol="0" wrapChar="" autoWrapLength="0" useMaxLineLengthForAutoWrap="1"/>
      <placement placement="0" placementFlags="10" dist="1.5" distUnits="MM" xOffset="0" yOffset="0" offsetType="0" quadOffset="4" rotationAngle="0" priority="5" repeatDistance="0" overlapHandling="PreventOverlap" allowDegraded="0"/>
      <rendering scaleVisibility="1" maximumScale="0" minimumScale="30000" fontMinPixelSize="3" fontMaxPixelSize="10000" upsidedownLabels="0" labelPerPart="0" mergeLines="0" obstacle="1" obstacleFactor="1" limitNumLabels="0" maxNumLabels="2000" drawLabels="1" displayAll="0"/>
      <dd_properties>
        <Option type="Map">
          <Option name="name" type="QString" value=""/>
          <Option name="properties"/>
          <Option name="type" type="QString" value="collection"/>
        </Option>
      </dd_properties>
    </settings>
  </labeling>
  <layerGeometryType>0</layerGeometryType>
</qgis>
