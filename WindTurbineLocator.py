import arcpy
import os, sys, datetime, time, math
import traceback
import WindUtils
from arcpy import env
from arcpy.sa import *

if arcpy.CheckExtension("Spatial") == "Available":
    arcpy.CheckOutExtension("Spatial")

#Constants
CELLSIZE = 10
OVERWRITE_OUTPUT = True
WIND_DIR = 270
BUFFER_RADIUS = 44
HUB_HEIGHT = 80
TURBINE_BLADE_LENGTH = 44
TURBINE_MEGAWATTS = 3
TURBINE_BUFFER_LAYER_DIST = "6000 FEET"
ELEV_BUFFER_LIMIT = 1000
CANDIDATE_LINE_DIST_INTERVAL = 328
CANDIDATE_LINE_DIST_LIMIT = 2297
ELIMINATE_PARTS_AREA = 5000000  #Eliminate parts smaller than this area.
METERS_TO_FEET = 3.2808399
#Temp or Output Layer Name Constants
CANDIDATE_LAYER = "CandidateLayer"
ELEV_POINT_LAYER = "ElevPointLayer"
STUDY_AREA_LAYER = "StudyAreaLayer"
TURBINE_LAYER = "ProposedTurbineLayer"
CANDIDATE_BUFFER_LAYER = "CandidateBufferLayer"
TEMP_BUFFER_LAYER = "TempBufferLayer"
WINDFARM_BOUNDARY_SHAPE_FIELD = "Shape_Area"

#User inputed variables
dataWorkspace = r"<Enter path>\OutputWorkspace.gdb"
demInputLayer = r"<Enter path>\WF_Turbine_Sample.gdb\NED_10m"
slopeInputLayer = r"<Enter path>\WF_Turbine_Sample.gdb\Slope_10m_per"
windFarmBoundaryLayer = r"<Enter path>\WF_Turbine_Sample.gdb\WindFarmSite"
minTotalMW = 90

# Set environment settings
arcpy.overwriteOutput = OVERWRITE_OUTPUT
env.cellSize = CELLSIZE
env.workspace = dataWorkspace

if env.scratchWorkspace == "" or env.scratchWorkspace is None:
    env.scratchWorkspace = env.workspace

scratchWS = env.scratchWorkspace

try:

    #wind direction is on different rotation
    adjustedWindDir = WIND_DIR + 90
    if adjustedWindDir > 360:
        adjustedWindDir = adjustedWindDir - 360
    oppositeWindDir = adjustedWindDir + 180

    #opposite wind direction
    if oppositeWindDir > 360:
        oppositeWindDir = oppositeWindDir - 360

    #Calulate the minimal area needed to obtain the minimum total MW required
    minStudyArea = ((TURBINE_BLADE_LENGTH * TURBINE_BLADE_LENGTH) * math.pi) * (minTotalMW / TURBINE_MEGAWATTS)
    arcpy.AddMessage("Min Study Area: " + str(minStudyArea))

    if arcpy.Exists(TURBINE_LAYER):
        arcpy.DeleteFeatures_management(TURBINE_LAYER)

    if arcpy.Exists(STUDY_AREA_LAYER):
        arcpy.Delete_management(STUDY_AREA_LAYER)

    if arcpy.Exists(CANDIDATE_LAYER):
        arcpy.Delete_management(CANDIDATE_LAYER)

    if arcpy.Exists(ELEV_POINT_LAYER):
        arcpy.Delete_management(ELEV_POINT_LAYER)

    #Create the output turbine layer
    spatial_reference = arcpy.Describe(demInputLayer).spatialReference
    arcpy.CreateFeatureclass_management(dataWorkspace, TURBINE_LAYER, "POINT", "", "", "", spatial_reference)

    #Requires ArcGIS Desktop Advanced
    #arcpy.AddMessage("Rebuilding polygons")
    #arcpy.EliminatePolygonPart_management("windfarm_memlyr", STUDY_AREA_LAYER, "AREA", ELIMINATE_PARTS_AREA, "", "CONTAINED_ONLY")

    #Only select areas that are greater or equal to the define minimum total MW
    arcpy.MakeFeatureLayer_management(windFarmBoundaryLayer, "studyarea_memlyr", WINDFARM_BOUNDARY_SHAPE_FIELD + " >=" + str(minStudyArea))
    
    arcpy.AddMessage("Extract Slope")
    slopeExtRaster = ExtractByMask(slopeInputLayer, "studyarea_memlyr")

    arcpy.AddMessage("Extract Raster by Attribute")
    attributeSlopeExtractRaster = ExtractByAttributes(slopeExtRaster, "VALUE < 20")

    arcpy.AddMessage("Extract Elevation")
    elevExtRaster = ExtractByMask(demInputLayer, attributeSlopeExtractRaster)

    arcpy.AddMessage("Converting to Points")
    arcpy.RasterToPoint_conversion(elevExtRaster, ELEV_POINT_LAYER, "VALUE")

    #extracts slope attributes from raster, using ELEV_POINT_LAYER, and creates a new layer
    arcpy.AddMessage("Extracting values to points")
    ExtractValuesToPoints(ELEV_POINT_LAYER, attributeSlopeExtractRaster, CANDIDATE_LAYER, "NONE", "VALUE_ONLY")

    arcpy.AddMessage("Add Fields")
    arcpy.AddField_management(CANDIDATE_LAYER, "Elev", "DOUBLE", 18, 4)
    arcpy.AddField_management(CANDIDATE_LAYER, "Slope", "DOUBLE", 18, 4)

    arcpy.AddMessage("Calc Fields")
    arcpy.CalculateField_management(CANDIDATE_LAYER, "Elev", "float(!grid_code!)", "PYTHON")
    arcpy.CalculateField_management(CANDIDATE_LAYER, "Slope", "float(!RASTERVALU!)", "PYTHON")

    #Cleanup - delete slopeExtRaster, attributeSlopeExtractRaster, and elvExt
    if arcpy.Exists(slopeExtRaster):
        arcpy.Delete_management(slopeExtRaster)

    if arcpy.Exists(attributeSlopeExtractRaster):
        arcpy.Delete_management(attributeSlopeExtractRaster)

    if arcpy.Exists(elevExtRaster):
        arcpy.Delete_management(elevExtRaster)

    #Get count of candidate points
    result = str(arcpy.GetCount_management(CANDIDATE_LAYER))

    arcpy.AddMessage("Time to check out these points - " + result)

    countRecordsProcessed = 0
    countTurbines = 0

    disqualifiedList = []

    insertCursor = arcpy.InsertCursor(TURBINE_LAYER)

    #Time to look at the whole layer
    candidateFields = ['OBJECTID', 'SHAPE@', 'Elev', 'Slope']
    with arcpy.da.SearchCursor(CANDIDATE_LAYER, candidateFields, where_clause="Slope < 2", sql_clause=(None, "ORDER BY Elev DESC")) as searchCursor:
        for row in searchCursor:
            id = str(row[0])

            #For testing
            #if countTurbines > 10:
            #    break;

            if countRecordsProcessed % 100 == 0 and countRecordsProcessed != 0:
                print str(countRecordsProcessed), "records processed"

            if (WindUtils.checkInList(disqualifiedList, id) == False):
                arcpy.AddMessage("Turbines Sited: " + str(countTurbines))
                arcpy.AddMessage("Total Disqualified: " + str(len(disqualifiedList)) + " - " + str(int(result) - len(disqualifiedList) - countTurbines) + " left")

                isValidCandidate = True
                candidateFeat = row[1]
                candidatePoint = candidateFeat.getPart(0)
                candidateCoords = str(candidatePoint.X) + " " + str(candidatePoint.Y)
                y1 = candidatePoint.Y
                x1 = candidatePoint.X

                #Genereate the 11.5 KM buffer - 37729.6 ft
                arcpy.AddMessage("Generating Buffer")
                turbBufferLayer = arcpy.CreateScratchName(CANDIDATE_BUFFER_LAYER, "", "FeatureClass", scratchWS)
                arcpy.Buffer_analysis(candidateFeat, turbBufferLayer, TURBINE_BUFFER_LAYER_DIST)

                arcpy.AddMessage("Zone Stats 1")
                zoneMinStats = ZonalStatistics(turbBufferLayer, "OBJECTID", demInputLayer,
                                         "MINIMUM", "DATA")

                arcpy.AddMessage("Zone Stats 2")
                zoneMaxStats = ZonalStatistics(turbBufferLayer, "OBJECTID", demInputLayer,
                                         "MAXIMUM", "DATA")

                arcpy.AddMessage("Get Min Elev")
                zMinElev = arcpy.GetCellValue_management(zoneMinStats, candidateCoords)

                arcpy.AddMessage("Get Max Elev")
                zMaxElev = arcpy.GetCellValue_management(zoneMaxStats, candidateCoords)

                line1 = []
                line2 = []

                #Cleanup temp layers
                if arcpy.Exists(turbBufferLayer):
                    arcpy.Delete_management(turbBufferLayer)

                if arcpy.Exists(zoneMinStats):
                    arcpy.Delete_management(zoneMinStats)

                if arcpy.Exists(zoneMaxStats):
                    arcpy.Delete_management(zoneMaxStats)

                arcpy.AddMessage("Elev diff: " + str(float(str(zMaxElev)) - float(str(zMinElev))))
                #Check the min and max elevation in the buffer layer
                if (float(str(zMaxElev)) - float(str(zMinElev)) <= ELEV_BUFFER_LIMIT):
                    arcpy.AddMessage("Passed Elev Diff test")
                    candidateElev = float(str(arcpy.GetCellValue_management(demInputLayer, candidateCoords)))
                    candidateElev += (HUB_HEIGHT - BUFFER_RADIUS)

                    candidateDistInterval = CANDIDATE_LINE_DIST_INTERVAL
                    upElevL = []
                    upSlopeL = []
                    downSlopeL = []
                    arcpy.AddMessage("Looping through dist")

                    while candidateDistInterval < CANDIDATE_LINE_DIST_LIMIT:
                        adjWindDirY = math.asin(math.sin(y1) * math.cos(candidateDistInterval) + math.cos(y1) * math.sin(candidateDistInterval) * math.cos(adjustedWindDir))
                        adjWindDirX = x1 + math.atan2(math.sin(adjustedWindDir) * math.sin(candidateDistInterval) * math.cos(y1), math.cos(candidateDistInterval) - math.sin(y1) * math.sin(adjWindDirY))

                        line1.append(str(adjWindDirX) + "," + str(adjWindDirY))

                        oppWindDirY = math.asin(math.sin(y1) * math.cos(candidateDistInterval) + math.cos(y1) * math.sin(candidateDistInterval) * math.cos(oppositeWindDir))
                        oppWindDirX = x1 + math.atan2(math.sin(oppositeWindDir) * math.sin(candidateDistInterval) * math.cos(y1), math.cos(candidateDistInterval) - math.sin(y1) * math.sin(adjWindDirY))

                        line2.append(str(oppWindDirX) + "," + str(oppWindDirY))

                        upElev =  str(arcpy.GetCellValue_management(demInputLayer, str(adjWindDirX) + " " + str(adjWindDirY)))
                        if (upElev != "NoData"):
                            upElevL.append(float(upElev))

                        upSlope = str(arcpy.GetCellValue_management(slopeInputLayer, str(adjWindDirX) + " " + str(adjWindDirY)))
                        if (upSlope != "NoData"):
                            upSlopeL.append(float(upSlope))

                        downSlope = str(arcpy.GetCellValue_management(slopeInputLayer, str(oppWindDirX) + " " + str(oppWindDirY)))
                        if (downSlope != "NoData"):
                            downSlopeL.append(float(downSlope))

                        candidateDistInterval = candidateDistInterval + CANDIDATE_LINE_DIST_INTERVAL

                    arcpy.AddMessage("Done looping")
                    minElev = 999999
                    maxElev = 0
                    for upElev in upElevL:
                        if (upElev < minElev):
                            minElev = upElev
                        if (upElev > maxElev):
                            maxElev = upElev

                    arcpy.AddMessage("Min Elev: " + str(minElev) + "   Max Elev: " + str(maxElev))

                    if ((float(str(candidateElev)) - float(str(zMinElev))) < (3 * (maxElev - minElev))):
                        isValidCandidate = False

                    arcpy.AddMessage("Checking Slope")

                    for slopeVal in upSlopeL:
                        if slopeVal > 2:
                            arcpy.AddMessage("Failed Up Slope: " + str(slopeVal))
                            isValidCandidate = False
                            break

                    for slopeVal in downSlopeL:
                        if slopeVal > 2:
                            arcpy.AddMessage("Failed Down Slope: " + str(slopeVal))
                            isValidCandidate = False
                            break
                else:
                    arcpy.AddMessage("Failed elevation test")
                    isValidCandidate = False

                if (isValidCandidate == False):
                    arcpy.AddMessage("Bad Candidate")
                    disqualifiedList.append(str(row[0]))
                else:
                    arcpy.AddMessage("Good Candidate")
                    insertRow = insertCursor.newRow()
                    insertRow.shape = row[1]
                    insertCursor.insertRow(insertRow)
                    countTurbines += 1

                    #Disqualify all points that fall in vicinity and path of the newly selected candidate
                    #Construct Line
                    lineArray = arcpy.Array()

                    i = len(line1) - 1

                    while i != -1:
                        if line1[i] != "":
                            coords = str(line1[i]).split(',')
                            pnt = arcpy.Point()
                            pnt.X = float(coords[0])
                            pnt.Y = float(coords[1])
                            lineArray.add(pnt)

                        i = i - 1

                    for item in line2:
                        if item != "":
                            coords = str(item).split(',')
                            pnt = arcpy.Point()
                            pnt.X = float(coords[0])
                            pnt.Y = float(coords[1])
                            lineArray.add(pnt)

                    #Construct the wind path based on the wind direction
                    candidatePolyline = arcpy.Polyline(lineArray)

                    arcpy.MakeFeatureLayer_management(CANDIDATE_LAYER, "candidate_memlyr")

                    candidateBuffer = arcpy.CreateScratchName(TEMP_BUFFER_LAYER, "", "FeatureClass", scratchWS)
                    arcpy.Buffer_analysis(candidateFeat, candidateBuffer, str((BUFFER_RADIUS * METERS_TO_FEET) * 10) + " feet")

                    candidatePathBuffer = arcpy.CreateScratchName(TEMP_BUFFER_LAYER, "", "FeatureClass", scratchWS)
                    arcpy.Buffer_analysis(candidatePolyline, candidatePathBuffer, str((BUFFER_RADIUS * METERS_TO_FEET) * 6) + " feet")

                    #Select points inside the candidate buffer and the candidate wind path buffer
                    arcpy.SelectLayerByLocation_management("candidate_memlyr", "INTERSECT", candidateBuffer, "", "NEW_SELECTION")
                    arcpy.SelectLayerByLocation_management("candidate_memlyr", "INTERSECT", candidatePathBuffer, "", "ADD_TO_SELECTION")

                    countDisqualPointsByBuffer = 0

                    #Add points within buffered areas to disqualified list
                    with arcpy.da.SearchCursor("candidate_memlyr", ["OBJECTID"]) as searchCheckCursor:
                        for chkrow in searchCheckCursor:
                            if str(chkrow[0]) != id:
                                disqualifiedList.append(str(chkrow[0]))
                                countDisqualPointsByBuffer += 1

                    arcpy.AddMessage("Disqualified by buffer: " + str(countDisqualPointsByBuffer))

                    arcpy.Delete_management("candidate_memlyr")
                    arcpy.Delete_management(candidateBuffer)
                    arcpy.Delete_management(candidatePathBuffer)

            countRecordsProcessed += 1

    del insertCursor
   
except:
    # Get the traceback object
    #
    tb = sys.exc_info()[2]
    tbinfo = traceback.format_tb(tb)[0]

    # Concatenate information together concerning the error into a message string
    #
    pymsg = "PYTHON ERRORS:\nTraceback info:\n" + tbinfo + "\nError Info:\n" + str(sys.exc_info()[1])
    msgs = "ArcPy ERRORS:\n" + arcpy.GetMessages(2) + "\n"
 
    # Return python error messages for use in script tool or Python Window
    #
    arcpy.AddError(pymsg)
    arcpy.AddError(msgs)
 
    # Print Python error messages for use in Python / Python Window
    #
    print pymsg + "\n"
    print msgs
 
arcpy.AddMessage("Done")
